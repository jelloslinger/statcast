from inspect import Parameter

import numpy as np
import pandas as pd

from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted
from sklearn.metrics import mean_squared_error

from rpy2.robjects.packages import importr
from rpy2.robjects import pandas2ri

from .base import BetterModel
from .spark import GridSearchCV

pandas2ri.activate()
rLME4 = importr('lme4')


class BetterLME4(BaseEstimator, RegressorMixin, BetterModel):

    _params = [Parameter('formulas', Parameter.POSITIONAL_OR_KEYWORD,
                         default=()),
               Parameter('LME4Params', Parameter.POSITIONAL_OR_KEYWORD,
                         default={})]

    def fit(self, X, Y):
        '''Doc String'''

        check_X_y(X, Y, multi_output=True, dtype=None)
        data = pd.concat((pd.DataFrame(X, columns=self.xLabels),
                          pd.DataFrame(Y, columns=self.yLabels)), axis=1)
        return self.fitD(data)

    def fitD(self, data):
        '''Doc String'''

        if not any((self.xLabels, self.yLabels, self.formulas)):
            raise RuntimeError('betterLME must have xLabels, yLabels, and '
                               'formulas defined')
        if isinstance(self.formulas, str):
            self.formulas = (self.formulas,)
        if len(self.formulas) != len(self.yLabels):
            if len(self.formulas) == 1:
                self.formulas = self.formulas * len(self.yLabels)
            else:
                raise RuntimeError('formulas must be a single string, or a '
                                   'tuple the same length as yLabels')
        X, Y = self.createX(data), self.createY(data)
        check_X_y(X, Y, multi_output=True, dtype=None)
        self.models_ = {}
        self.factors_ = {}
        for ii, yLabel in enumerate(self.yLabels):
            subData = pd.concat((X, Y[yLabel]), axis=1)
            formula = yLabel + ' ~ ' + self.formulas[ii]
            model = rLME4.lmer(formula=formula,
                               data=subData,
                               **self.LME4Params)
            self.models_[yLabel] = model
            self.factors_[yLabel] = self._factor(model)

        return self

    def createX(self, data):
        '''Doc String'''

        X = data[self.xLabels].copy()
        for xLabel in self.xLabels:
            if X[xLabel].dtype is pd.api.types.CategoricalDtype():
                X[xLabel] = X[xLabel].astype(X[xLabel].cat.categories.dtype)

        return X

    @staticmethod
    def _factor(model):
        '''Doc String'''

        rEffs = rLME4.random_effects(model)
        fEffs = rLME4.fixed_effects(model)
        factor = {}

        for elem, name in zip(rEffs, rEffs.names):
            factor[name] = pandas2ri.ri2py(elem)

        for elem, name in zip(fEffs, fEffs.names):
            factor[name] = elem

        return factor

    def predictD(self, data):
        '''Doc String'''

        check_is_fitted(self, ['models_', 'factors_'])

        X = self.createX(data)
        check_array(X, dtype=None)

        Y = pd.DataFrame()
        for yLabel in self.yLabels:
            Y[yLabel] = \
                pandas2ri.ri2py(rLME4.predict_merMod(self.models_[yLabel],
                                                     newdata=X,
                                                     allow_new_levels=True))

        return Y

    def predict(self, X):
        '''Doc String'''

        check_array(X, dtype=None)
        return self.predictD(pd.DataFrame(X, columns=self.xLabels))

    def score(self, X, Y, sample_weight=None):
        '''Doc String'''

        Y = check_array(Y)
        Yp = self.predict(X)
        return -np.sqrt([mean_squared_error(y, yp, sample_weight)
                         for y, yp in zip(Y.T, Yp.values.T)]).mean()

    def chooseFormula(self, data, formulas, n_jobs=1, cv=None, refit=True):
        '''Doc String'''

        self.cv_results_ = []
        yLabels = self.yLabels
        formulaChoices = []
        param_grid = {'formulas': formulas}
        for yLabel in yLabels:
            self.yLabels = [yLabel]

            result = GridSearchCV(self, param_grid,
                                  n_jobs=n_jobs, cv=cv, refit=False). \
                fit(self.createX(data), self.createY(data))
            formulaChoices.append(result.best_params_['formulas'])
            self.cv_results_.append(result.cv_results_)

        self.formulas = formulaChoices
        self.yLabels = yLabels

        if refit:
            self.fitD(data)

        return self
