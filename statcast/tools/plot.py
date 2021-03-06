import os

import numpy as np
import pandas as pd
from scipy import stats
from matplotlib import pyplot as plt
from matplotlib import lines as mlines

try:
    from PIL import Image as pilimg
except ImportError:
    imaging = False
else:
    imaging = True

from sklearn.metrics import precision_recall_curve

from ..better.kde import BetterKernelDensity

from . import __path__

plt.style.use(os.path.join(os.path.dirname(__path__[0]),
                           'data', 'blackontrans.mplstyle'))


def correlationPlot(Y, Yp, labels=None, units=None, **plotParams):
    '''Doc String'''

    # Handle Pandas DataFrames
    if isinstance(Y, pd.DataFrame):
        if labels is None:
            labels = list(Y.columns)
        Y = Y.values
    if isinstance(Yp, pd.DataFrame):
        Yp = Yp.values

    # Handle 1D arrays
    if Y.ndim == 1:
        Y = Y[:, None]
    if Yp.ndim == 1:
        Yp = Yp[:, None]

    # Handle row vectors
    if Y.shape[0] == 1:
        Y = Y.T
    if Yp.shape[0] == 1:
        Yp = Yp.T

    # Handle no label or unit inputs
    if labels is None:
        labels = [None for dummy in range(Y.shape[1])]
    if units is None:
        units = [None for dummy in range(Y.shape[1])]

    figs = []

    for y, yp, label, unit in zip(Y.T, Yp.T,
                                  labels, units):
        rmsErr = np.sqrt(np.mean((y - yp) ** 2))
        r2 = stats.pearsonr(y, yp)[0] ** 2
        mae = np.mean(np.abs(y - yp))

        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(y, yp, '.', **plotParams)

        if unit is not None:
            ax.set_xlabel('Actual ({})'.format(unit))
            ax.set_ylabel('Prediction ({})'.format(unit))
        else:
            ax.set_xlabel('Actual')
            ax.set_ylabel('Prediction')

        if label is not None:
            ax.set_title(label)

        axLims = list(ax.axis())
        axLims[0] = axLims[2] = min(axLims[0::2])
        axLims[1] = axLims[3] = max(axLims[1::2])
        ax.axis(axLims)
        ax.plot(axLims[:2], axLims[2:],
                '--', color=plt.rcParams['lines.color'], linewidth=1)

        labels = ['{}: {:.2f}'.format(name, stat)
                  for name, stat in zip(['RMSE', 'R2', 'MAE'],
                                        [rmsErr, r2, mae])]
        addText(ax, labels, loc='lower right')

        figs.append(fig)

    return figs


def addText(ax, text, loc='best', **kwargs):
    '''Doc String'''

    if 'right' in loc:
        markerfirst = False
    else:
        markerfirst = True

    handles = [mlines.Line2D([], [], alpha=0.0)] * len(text)
    ax.legend(handles=handles, labels=text, loc=loc, frameon=False,
              handlelength=0, handletextpad=0, markerfirst=markerfirst,
              **kwargs)
    return


def plotKDHist(data, kernel='epanechnikov', bandwidth=None, alpha=5e-2,
               ax=None, n_jobs=1, cv=None):
    '''Doc String'''

    if data.ndim < 2:
        data = data[:, None]
    xmin, xmax = min(data), max(data)

    if bandwidth is None:
        kde = BetterKernelDensity(kernel=kernel, rtol=1e-4,
                                  normalize=False).fit(data)
        kde.selectBandwidth(n_jobs=n_jobs, cv=cv)
    else:
        kde = BetterKernelDensity(kernel=kernel, rtol=1e-4,
                                  normalize=False,
                                  bandwidth=bandwidth).fit(data)

    xFit = np.linspace(xmin - kde.bandwidth, xmax + kde.bandwidth, 1e3)
    yFit = kde.predict(xFit[:, None])
    fitL, fitU = kde.confidence(xFit[:, None], alpha=alpha)

    if ax is not None:
        ax.plot(xFit, yFit * 100)
        ax.fill_between(xFit, fitU * 100, fitL * 100, alpha=0.35, lw=0,
                        label='{:.0f}% Confidence Interval'.
                        format(1e2 * (1 - alpha)))
        return ax, kde

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(xFit, yFit * 100)
    ax.fill_between(xFit, fitU * 100, fitL * 100, alpha=0.35, lw=0,
                    label='{:.0f}% Confidence Interval'.
                    format(1e2 * (1 - alpha)))

    try:
        ax.set_xlabel(data.name)
    except AttributeError:
        pass

    ax.set_ylabel('Probability Density (%)')
    ax.set_xlim(left=xmin - kde.bandwidth, right=xmax + kde.bandwidth)
    ax.set_ylim(bottom=0, auto=True)
    return fig, kde


def plotPrecRec(y, yp, ax=None, label=None):
    '''Doc String'''

    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)

    if y.shape[0] != yp.shape[0]:
        raise Exception('Number of rows in y & yp must match')

    prec, rec, _ = precision_recall_curve(y, yp)

    ax.plot(rec, prec, label=label)
    ax.set_xlabel('Recall')
    ax.set_ylabel('Precision')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    try:
        return fig
    except NameError:
        return ax


def plotPrecRecMN(y, yp, ax=None, labels=None):
    '''Doc String'''

    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)

    if y is pd.api.types.CategoricalDtype():
        classes = sorted(y.cat.categories)
    else:
        classes = np.unique(y)

    if labels is None:
        labels = classes

    if not classes.shape[0] == yp.shape[1] == len(labels):
        raise Exception('Number of classes in y must match number of '
                        'columns in yp and number labels.')
    elif y.shape[0] != yp.shape[0]:
        raise Exception('Number of rows in y & yp must match.')

    prec = {}
    rec = {}
    Y = []

    for i, klass in enumerate(classes):
        yi = y == klass
        Y.append(yi)
        prec[klass], rec[klass], _ = precision_recall_curve(yi, yp[:, i])

    Y = np.array(Y)
    prec['micro'], rec['micro'], _ = \
        precision_recall_curve(Y.ravel(), yp.ravel())

    ax.plot(rec['micro'] * 100, prec['micro'] * 100, label='micro-average')

    for klass, label in zip(classes, labels):
        ax.plot(rec[klass] * 100, prec[klass] * 100, label=label)

    ax.legend()
    ax.set_xlabel('Recall (%)')
    ax.set_ylabel('Precision (%)')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    try:
        return fig
    except NameError:
        return ax


def plotResiduals(X, Y, Yp, xLabels=None, xUnits=None, yLabels=None,
                  yUnits=None, pltParams={}):

    if X.ndim == 1:
        X = X[:, None]

    if Y.ndim == 1:
        Y = Y[:, None]

    if Yp.ndim == 1:
        Yp = Yp[:, None]

    if Y.shape != Yp.shape:
        raise Exception('Y ({}) and Yp ({}) '
                        'must have same dimensions'.format(Y.shape, Yp.shape))

    if X.shape[0] != Y.shape[0]:
        raise Exception('X ({}) and Y ({}) must have same number of '
                        'rows'.format(X.shape[0], Y.shape[0]))

    if xLabels is None:
        try:
            xLabels = list(X.columns)
        except AttributeError:
            xLabels = [''] * X.shape[1]
    elif len(xLabels) != X.shape[1]:
        raise Exception('xLabels must have same length ({}) as the number of '
                        'columns of X ({})'.format(len(xLabels), X.shape[1]))
    else:
        xLabels = list(xLabels)

    if xUnits is not None:
        if len(xUnits) != len(xLabels):
            raise Exception('xUnits must have same length ({}) '
                            'as xLabels ({}) if supplied'.format(len(xUnits),
                                                                 len(xLabels)))
        for i, xUnit in enumerate(xUnits):
            xLabels[i] += ' ({})'.format(xUnit)

    if yLabels is None:
        try:
            yLabels = list(Y.columns)
        except AttributeError:
            yLabels = [''] * Y.shape[1]
    elif len(yLabels) != Y.shape[1]:
        raise Exception('yLabels must have same length ({}) as the number of '
                        'columns of Y ({})'.format(len(yLabels), Y.shape[1]))
    else:
        yLabels = list(yLabels)

    yLabels = [yLabel + ' Error' for yLabel in yLabels]

    if yUnits is not None:
        if len(yUnits) != len(yLabels):
            raise Exception('yUnits must have same length ({}) '
                            'as yLabels ({}) if supplied'.format(len(yUnits),
                                                                 len(yLabels)))
        for i, yUnit in enumerate(yUnits):
            yLabels[i] += ' ({})'.format(yUnit)

    figs = []
    for i, xLabel in enumerate(xLabels):
        fig = plt.figure(figsize=(10.21, 3 * len(yLabels)))
        for j, yLabel in enumerate(yLabels):
            ax = fig.add_subplot(len(yLabels), 1, j + 1)
            ax.plot(X[:, i], Yp[:, j] - Y[:, j], '.', **pltParams)
            ax.set_ylabel(yLabel)
        ax.set_xlabel(xLabel)
        figs.append(fig)

    return figs


if imaging:
    def plotImages(X, Y, images, sizes=20, alphas=1, ax=None):
        '''Doc String'''

        if not isinstance(sizes, (list, tuple)):
            sizes = (sizes,) * len(X)
        if not isinstance(images, (list, tuple)):
            images = (images,) * len(X)
        if not isinstance(alphas, (list, tuple)):
            alphas = (alphas,) * len(X)

        ims = [pilimg.open(image) for image in images]

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(1, 1, 1)

        # plot and set axis limits
        ax.plot(X, Y, 'o', mfc='None', mec='None', markersize=max(sizes))
        ax.axis(ax.axis())

        for size, im, alpha, x, y in zip(sizes, ims, alphas, X, Y):
            offsetsPx = np.array([sz / max(im.size) * size / 72 / 2 *
                                  ax.get_figure().dpi for sz in im.size])
            pxPerUnit = ax.transData.transform((1, 1)) - \
                ax.transData.transform((0, 0))
            offsetsUnit = offsetsPx / pxPerUnit
            extent = (x - offsetsUnit[0], x + offsetsUnit[0],
                      y - offsetsUnit[1], y + offsetsUnit[1])
            ax.imshow(im, alpha=alpha, extent=extent, aspect='auto',
                      interpolation='bilinear')

        try:
            return fig
        except NameError:
            return ax
