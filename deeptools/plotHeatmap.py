#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
import argparse
from collections import OrderedDict
import numpy as np
from matplotlib import use
use('Agg')
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import FontProperties
import matplotlib.gridspec as gridspec

# own modules
from deeptools import parserCommon
from deeptools import heatmapper
from deeptools.heatmapper_utilities import plot_single, getProfileTicks

debug = 0
plt.ioff()


def parse_arguments(args=None):
    parser = argparse.ArgumentParser(
        parents=[parserCommon.heatmapperMatrixArgs(),
                 parserCommon.heatmapperOutputArgs(mode='heatmap'),
                 parserCommon.heatmapperOptionalArgs(mode='heatmap')],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='This tool creates a heatmap for a '
        'score associated to genomic regions. '
        'The program requires a preprocessed matrix '
        'generated by the tool computeMatrix.',
        epilog='An example usage is: plotHeatmap -m <matrix file>',
        add_help=False)

    return parser


def process_args(args=None):
    args = parse_arguments().parse_args(args)

    # Because of galaxy, the value of this variables is normally
    # set to ''. Therefore this check is needed
    for attr in ['zMin', 'zMax', 'yMax', 'yMin']:
        try:
            args.__setattr__(attr, float(args.__getattribute__(attr)))
        # except ValueError, TypeError:
        except:
            args.__setattr__(attr, None)

    args.heatmapHeight = args.heatmapHeight if args.heatmapHeight > 3 and args.heatmapHeight <= 100 else 10

    if not matplotlib.colors.is_color_like(args.missingDataColor):
        print "The value {0}  for --missingDataColor is "
        "not valid".format(args.missingDataColor)
        exit(1)

    if args.regionsLabel != 'genes':
        args.regionsLabel = \
            [x.strip() for x in args.regionsLabel.split(',')]

    else:
        args.regionsLabel = []

    return args


def get_heatmap_ticks(hm, reference_point_label, startLabel, endLabel):
    """
    returns the position and labelling of the xticks that
    correspond to the heatmap
    """
    w = hm.parameters['bin size']
    b = hm.parameters['upstream']
    a = hm.parameters['downstream']
    m = hm.parameters['body']

    if b < 1e5:
        quotient = 1000
        symbol = 'Kb'
    else:
        quotient = 1e6
        symbol = 'Mb'

    if m == 0:
        xticks = [(k / w) for k in [0, b, b + a]]
        xticks_label = ['{0:.1f}'.format(-(float(b) / quotient)), reference_point_label,
                        '{0:.1f}{1}'.format(float(a) / quotient, symbol)]

    else:
        xticks_values = [0]
        xticks_label = []

        # only if upstream region is set, add a x tick
        if hm.parameters['upstream'] > 0:
            xticks_values.append(b)
            xticks_label.append('{0:.1f}'.format(-(float(b) / quotient)))

        # set the x tick for the body parameter, regardless if
        # upstream is 0 (not set)
        xticks_values.append(b + m)
        xticks_label.append(startLabel)
        xticks_label.append(endLabel)
        if a > 0:
            xticks_values.append(b + m + a)
            xticks_label.append('{0:.1f}{1}'.format(float(a) / quotient, symbol))

        xticks = [k / w for k in xticks_values]

    return xticks, xticks_label


def prepare_layout(hm_matrix, heatmapsize, showSummaryPlot, showColorbar, perGroup):
    """
    prepare the plot layout
    as a grid having as many rows
    as samples (+1 for colobar)
    and as many rows as groups (or clusters) (+1 for profile plot)
    """
    heatmapwidth, heatmapheight = heatmapsize

    numcols = hm_matrix.get_num_samples()
    numrows = hm_matrix.get_num_groups()
    if perGroup:
        temp = numcols
        numcols = numrows
        numrows = temp

    # the rows have different size depending
    # on the number of regions contained in the
    if perGroup:
        # heatmap
        height_ratio = np.array([np.amax(np.diff(hm_matrix.group_boundaries))] * numrows)
        # scale ratio to sum = heatmapheight
        height_ratio = heatmapheight * (height_ratio.astype(float) / height_ratio.sum())
    else:
        # heatmap
        height_ratio = np.diff(hm_matrix.group_boundaries)
        # scale ratio to sum = heatmapheight
        height_ratio = heatmapheight * (height_ratio.astype(float) / height_ratio.sum())
    # the width ratio is equal for all heatmaps
    width_ratio = [heatmapwidth] * numcols

    if showColorbar:
        numcols += 1
        width_ratio += [1 / 2.54]
    if showSummaryPlot:
        numrows += 2  # plus 2 because an spacer is added
        # make height of summary plot
        # proportional to the width of heatmap
        sumplot_height = heatmapwidth
        spacer_height = heatmapwidth / 10
        # scale height_ratios to convert from row
        # numbers to heatmapheigt fractions
#        height_ratio = heatmapheight * (height_ratio/sum(height_ratio))
        height_ratio = np.concatenate([[sumplot_height, spacer_height],
                                       height_ratio])

    grids = gridspec.GridSpec(numrows, numcols, height_ratios=height_ratio, width_ratios=width_ratio)

    return grids


def plotMatrix(hm, outFileName,
               colorMapDict={'colorMap': 'binary', 'missingDataColor': 'black'},
               plotTitle='',
               xAxisLabel='', yAxisLabel='', regionsLabel='',
               zMin=None, zMax=None,
               yMin=None, yMax=None,
               averageType='median',
               reference_point_label='TSS',
               startLabel='TSS', endLabel="TES",
               heatmapHeight=25,
               heatmapWidth=7.5,
               perGroup=False, whatToShow='plot, heatmap and colorbar',
               plotType='simple',
               image_format=None,
               legend_location='upper-left'):

    matrix_flatten = None
    if zMin is None:
        matrix_flatten = hm.matrix.flatten()
        # try to avoid outliers by using np.percentile
        zMin = np.percentile(matrix_flatten, 1.0)
        if np.isnan(zMin):
            zMin = None

    if zMax is None:
        if matrix_flatten is None:
            matrix_flatten = hm.matrix.flatten()
        # try to avoid outliers by using np.percentile
        zMax = np.percentile(matrix_flatten, 98.0)
        if np.isnan(zMax):
            zMax = None

    plt.rcParams['font.size'] = 8.0
    fontP = FontProperties()
#    fontP.set_size('small')

    showSummaryPlot = False
    showColorbar = False

    if whatToShow == 'plot and heatmap':
        showSummaryPlot = True
    elif whatToShow == 'heatmap and colorbar':
        showColorbar = True
    else:
        showSummaryPlot = True
        showColorbar = True

    grids = prepare_layout(hm.matrix, (heatmapWidth, heatmapHeight),
                           showSummaryPlot, showColorbar, perGroup)

    # figsize: w,h tuple in inches
    figwidth = heatmapWidth / 2.54
    figheight = heatmapHeight / 2.54
    if showSummaryPlot:
        # the summary plot ocupies a height
        # equal to the fig width
        figheight += figwidth

    numsamples = hm.matrix.get_num_samples()
    total_figwidth = figwidth * numsamples
    if showColorbar:
        total_figwidth += 1 / 2.54
    fig = plt.figure(figsize=(total_figwidth, figheight))

    hm.parameters['upstream']
    hm.parameters['downstream']
    hm.parameters['body']
    hm.parameters['bin size']

    xticks, xtickslabel = getProfileTicks(hm, reference_point_label, startLabel, endLabel)

    xticks_heat, xtickslabel_heat = get_heatmap_ticks(hm, reference_point_label, startLabel, endLabel)
    fig.suptitle(plotTitle, y=1 - (0.06 / figheight))

    # colormap for the heatmap
    if colorMapDict['colorMap']:
        cmap = plt.get_cmap(colorMapDict['colorMap'])
    if colorMapDict['colorList'] and len(colorMapDict['colorList']) > 0:
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
            'my_cmap', colorMapDict['colorList'], N=colorMapDict['colorNumber'])

    # color map for the summary plot (profile) on top of the heatmap
    cmap_plot = plt.get_cmap('jet')
    numgroups = hm.matrix.get_num_groups()
    if perGroup:
        color_list = cmap_plot(np.arange(hm.matrix.get_num_samples()) / hm.matrix.get_num_samples())
    else:
        color_list = cmap_plot(np.arange(numgroups) / numgroups)
    cmap.set_bad(colorMapDict['missingDataColor'])  # nans are printed using this color

    # check if matrix is reference-point based using the upstream >0 value
    # and is sorted by region length. If this is
    # the case, prepare the data to plot a border at the regions end
    if hm.parameters['upstream'] > 0 and \
            hm.matrix.sort_using == 'region_length' and \
            hm.matrix.sort_method != 'no':

            _regions = hm.matrix.get_regions()
            regions_length_in_bins = []
            for _group in _regions:
                _reg_len = []
                for ind_reg in _group:
                    _len = ind_reg['end'] - ind_reg['start']
                    _reg_len.append((hm.parameters['upstream'] + _len) / hm.parameters['bin size'])
#                    print hm.parameters['upstream'] + (_len / hm.parameters['bin size'])
                regions_length_in_bins.append(_reg_len)
    else:
        regions_length_in_bins = None

    first_group = 0  # helper variable to place the title per sample/group
    for sample in range(hm.matrix.get_num_samples()):
        sample_idx = sample
        for group in range(numgroups):
            group_idx = group
            # add the respective profile to the
            # summary plot
            sub_matrix = hm.matrix.get_matrix(group, sample)
            if showSummaryPlot:
                if perGroup:
                    sample_idx = sample + 2  # plot + spacer
                else:
                    group += 2  # plot + spacer
                first_group = 1

            if perGroup:
                ax = fig.add_subplot(grids[sample_idx, group])
            else:
                ax = fig.add_subplot(grids[group, sample])
            if group == first_group and not showSummaryPlot and not perGroup:
                title = hm.matrix.sample_labels[sample]
                ax.set_title(title)

            rows, cols = sub_matrix['matrix'].shape
            interpolation_type = 'bicubic' if rows > 200 and \
                cols > 1000 else 'nearest'
            img = ax.imshow(sub_matrix['matrix'],
                            aspect='auto',
                            interpolation=interpolation_type,
                            origin='upper',
                            vmin=zMin,
                            vmax=zMax,
                            cmap=cmap,
                            extent=[0, cols, rows, 0])
            # plot border at the end of the regions
            # if ordered by length
            if regions_length_in_bins is not None:
                x_lim = ax.get_xlim()
                y_lim = ax.get_ylim()

                ax.plot(regions_length_in_bins[group_idx],
                        np.arange(len(regions_length_in_bins[group_idx])),
                        '--', color='black', linewidth=0.5, dashes=(3, 2))
                ax.set_xlim(x_lim)
                ax.set_ylim(y_lim)

            if perGroup:
                ax.axes.set_xlabel(sub_matrix['group'])
                if sample < hm.matrix.get_num_samples() - 1:
                    ax.axes.get_xaxis().set_visible(False)
            else:
                ax.axes.get_xaxis().set_visible(False)
                ax.axes.set_xlabel(xAxisLabel)
            ax.axes.set_yticks([])
            if perGroup and group == 0:
                ax.axes.set_ylabel(sub_matrix['sample'])
            elif not perGroup and sample == 0:
                ax.axes.set_ylabel(sub_matrix['group'])

        # add xticks to the bottom heatmap (last group)
        ax.axes.get_xaxis().set_visible(True)
        ax.axes.set_xticks(xticks_heat)
        ax.axes.set_xticklabels(xtickslabel_heat, size=8)

        # align the first and last label
        # such that they don't fall off
        # the heatmap sides
        ticks = ax.xaxis.get_major_ticks()
        ticks[0].label1.set_horizontalalignment('left')
        ticks[-1].label1.set_horizontalalignment('right')

        ax.get_xaxis().set_tick_params(
            which='both',
            top='off',
            direction='out')

    # plot the profiles on top of the heatmaps
    if showSummaryPlot:
        ax_list = []
        if perGroup:
            iterNum = numgroups
        else:
            iterNum = hm.matrix.get_num_samples()
        # plot each of the profiles
        for sample_id in range(iterNum):
            if perGroup:
                title = hm.matrix.group_labels[sample_id]
            else:
                title = hm.matrix.sample_labels[sample_id]
            if sample_id > 0:
                ax_profile = fig.add_subplot(grids[0, sample_id],
                                             sharey=ax_list[0])
            else:
                ax_profile = fig.add_subplot(grids[0, sample_id])

            ax_profile.set_title(title)
            if perGroup:
                iterNum2 = hm.matrix.get_num_samples()
            else:
                iterNum2 = numgroups
            for group in range(iterNum2):
                if perGroup:
                    sub_matrix = hm.matrix.get_matrix(sample_id, group)
                    line_label = sub_matrix['sample']
                else:
                    sub_matrix = hm.matrix.get_matrix(group, sample_id)
                    line_label = sub_matrix['group']
                plot_single(ax_profile, sub_matrix['matrix'],
                            averageType,
                            color_list[group],
                            line_label,
                            plot_type='simple')

            if sample_id > 0:
                plt.setp(ax_profile.get_yticklabels(), visible=False)

            if sample_id == 0 and yAxisLabel != '':
                ax_profile.set_ylabel(yAxisLabel)
            ax_profile.axes.set_xticks(xticks)
            ax_profile.axes.set_xticklabels(xtickslabel)
            ax_list.append(ax_profile)

            # align the first and last label
            # such that they don't fall off
            # the heatmap sides
            ticks = ax_profile.xaxis.get_major_ticks()
            ticks[0].label1.set_horizontalalignment('left')
            ticks[-1].label1.set_horizontalalignment('right')

        # reduce the number of yticks by half
        num_ticks = len(ax_list[0].get_yticks())
        yticks = [ax_list[0].get_yticks()[i] for i in range(1, num_ticks, 2)]
        ax_list[0].set_yticks(yticks)
        ax_list[0].set_ylim(yMin, yMax)
        if legend_location != 'none':
            ax_list[-1].legend(loc=legend_location.replace('-', ' '), ncol=1, prop=fontP,
                               frameon=False, markerscale=0.5)

    if showColorbar:
        if showSummaryPlot:
            # we dont want to colorbar to extend
            # over the profiles row
            grid_start = 2
        else:
            grid_start = 0

        ax = fig.add_subplot(grids[grid_start:, -1])
        fig.colorbar(img, cax=ax)

    plt.subplots_adjust(wspace=0.05, hspace=0.025, top=0.85,
                        bottom=0, left=0.04, right=0.96)

    plt.savefig(outFileName, bbox_inches='tight', pdd_inches=0, dpi=200,
                format=image_format)


def mergeSmallGroups(matrixDict):
    group_lengths = [len(x) for x in matrixDict.values()]
    min_group_length = sum(group_lengths) * 0.01

    to_merge = []
    i = 0
    _mergedHeatMapDict = OrderedDict()

    for label, ma in matrixDict.iteritems():
        # merge small groups together
        # otherwise visualization is impaired
        if group_lengths[i] > min_group_length:
            if len(to_merge):
                to_merge.append(label)
                new_label = " ".join(to_merge)
                new_ma = np.concatenate([matrixDict[item]
                                        for item in to_merge], axis=0)
            else:
                new_label = label
                new_ma = matrixDict[label]

            _mergedHeatMapDict[new_label] = new_ma
            to_merge = []
        else:
            to_merge.append(label)
        i += 1
    if len(to_merge) > 1:
        new_label = " ".join(to_merge)
        new_ma = np.array()
        for item in to_merge:
            new_ma = np.concatenate([new_ma, matrixDict[item]])
        _mergedHeatMapDict[new_label] = new_ma

    return _mergedHeatMapDict


def main(args=None):
    args = process_args(args)
    hm = heatmapper.heatmapper()
    matrix_file = args.matrixFile.name
    args.matrixFile.close()
    hm.read_matrix_file(matrix_file, default_group_name=args.regionsLabel)

    if args.kmeans is not None:
        hm.matrix.hmcluster(args.kmeans, method='kmeans')
    else:
        if args.hclust is not None:
            print "Performing hierarchical clustering." \
                  "Please note that it might be very slow for large datasets.\n"
            hm.matrix.hmcluster(args.hclust, method='hierarchical')

    group_len_ratio = np.diff(hm.matrix.group_boundaries) / len(hm.matrix.regions)
    if np.any(group_len_ratio < 5.0 / 1000):
        problem = np.flatnonzero(group_len_ratio < 5.0 / 1000)
        group_len = np.diff(hm.matrix.group_boundaries)
        print "Group '{}' contains too few regions {}. It can't "\
            "be plotted. Try removing this group.\n".format(hm.matrix.group_labels[problem[0]],
                                                            group_len[problem])
        if args.outFileSortedRegions:
            hm.save_BED(args.outFileSortedRegions)
            print 'Clustered output written in : ' + args.outFileSortedRegions.name
        else:
            print "No Output file defined for sorted regions. Please re-run "\
                  "heatmapper with --outFileSortedRegions to save the clustered output. "
        exit(1)

    if len(args.regionsLabel):
        hm.matrix.set_group_labels(args.regionsLabel)

    if args.samplesLabel and len(args.samplesLabel):
        hm.matrix.set_sample_labels(args.samplesLabel)

    if args.sortRegions != 'no':
        hm.matrix.sort_groups(sort_using=args.sortUsing,
                              sort_method=args.sortRegions)

    if args.outFileNameMatrix:
        hm.save_matrix_values(args.outFileNameMatrix)

    # if args.outFileNameData:
    #    hm.saveTabulatedValues(args.outFileNameData)

    if args.outFileSortedRegions:
        hm.save_BED(args.outFileSortedRegions)

    colormap_dict = {'colorMap': args.colorMap,
                     'colorList': args.colorList,
                     'colorNumber': args.colorNumber,
                     'missingDataColor': args.missingDataColor}

    plotMatrix(hm,
               args.outFileName,
               colormap_dict, args.plotTitle,
               args.xAxisLabel, args.yAxisLabel, args.regionsLabel,
               args.zMin, args.zMax,
               args.yMin, args.yMax,
               args.averageTypeSummaryPlot,
               args.refPointLabel,
               args.startLabel,
               args.endLabel,
               args.heatmapHeight,
               args.heatmapWidth,
               args.perGroup,
               args.whatToShow,
               image_format=args.plotFileFormat,
               legend_location=args.legendLocation)
