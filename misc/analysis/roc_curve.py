import seaborn as sns
sns.set(style="darkgrid")

import numpy as np
from sklearn import metrics
import matplotlib.pyplot as plt
from sklearn.metrics.ranking import _binary_clf_curve
import sys
import pandas
from matplotlib import rc

if len(sys.argv) < 2:
    print("please specify csv file as the first argument")

analysis_file = sys.argv[1]

# all parameters

IgA_name = 'IgA_ratio_of_q0.5_of_means'
IgM_name = "IgM_ratio_of_q0.5_of_means"
IgG_name = "IgG_ratio_of_q0.5_of_means"
score_names = [IgA_name, IgG_name, IgM_name]
label_name = "cohort_type"
plate_name = "plate_name"
time_name = "days_after_onset"
ctype_name = "cohort_id"

time_thresholds = ((0, 10), (11, 14), (15, 10000))
time_thresholds_roc = ((15, 10000), )

cr2marker = {1: "<",
             10: "*"}

remove_IgA_for_quality_control = ("B92", "B60", "B22", "B103", "CMV11", "CMV30", "EBV32", "EBV51", "EBV54", "EBV59")

histogram_bins = bins = np.linspace(1., 5, 30)
prior_probability_of_disease = 0.5
# cost_ratios = [1, 10]
cost_ratios = [10]


def label_of_cohort(cohort_type):
    return 1. if cohort_type == "positive" else 0.


def get_time_label(t_low, t_high):
    label = f'{t_low}-{t_high} days post symptom onset'
    if t_high == 10000:
        label = f'>{t_low-1} days post symptom onset'
    elif t_low == 0:
        label = f'<{t_high+1} days post symptom onset'

    return label


def remove_unlabeled(score_data):
    unlabeled = score_data[~score_data['cohort'].isin(('A', 'B', 'C', 'Z'))]
    score_data.drop(unlabeled.index, inplace=True)

def remove_longitudinal_study(score_data):
    # unlabeled = score_data[~score_data['cohort'].isin(('A', 'B', 'E', 'C', 'Z'))]
    longitudinal = score_data[ctype_name].str.contains('C[0-9]*$')
    score_data.drop(score_data[longitudinal].index, inplace=True)

def remove_plates45(score_data):
    plates45 = score_data[plate_name].str.contains('^plate9_[4-5]')
    score_data.drop(score_data[plates45].index, inplace=True)


def add_ytrue(score_data):
    label_dictionary = {"control": 0,
                        "unknown": 0,
                        "positive": 1}
    score_data['ytrue'] = score_data[label_name].replace(label_dictionary)


def remove_double_igg_entries(score_data):
    report = dict((sn, {}) for sn in score_names)

    for patient in score_data[ctype_name].unique():

        patient_data = score_data[score_data[ctype_name] == patient]

        for sn in score_names:

            selection = patient_data[patient_data[sn].notnull()]

            if len(selection) > 1:
                keep_index = selection.index[:1]
                remove_index = selection.index[1:]
                score_data.loc[keep_index, sn] = np.mean(selection[sn])
                score_data.loc[remove_index, sn] = np.nan

                if len(selection) > 2 or (len(selection) > 1 and sn != IgG_name):
                    report[sn][patient] = len(selection)

                # make sure we have edited the database and not a copy
                assert(len(score_data[score_data[ctype_name] == patient][sn].dropna()) == 1)

    print("channel cohort_id number_of_measurements")
    for k1 in report:
        for k2 in report[k1]:
            print(k1[:3], k2, report[k1][k2])
    print("-------------------------------------")


def parse_csv(file, score_names):
    score_data = pandas.read_csv(file)

    # quality control by Vibor
    # Vibor: I did however manually cleaned the IgA results by removing those with dotty pattern
    quality_control_iga_outliers = score_data[score_data[IgA_name].notnull() &
                                              score_data[ctype_name].isin(remove_IgA_for_quality_control)]
    score_data.loc[quality_control_iga_outliers.index, IgA_name] = np.nan

    remove_unlabeled(score_data)
    remove_longitudinal_study(score_data)
    remove_plates45(score_data)
    add_ytrue(score_data)
    remove_double_igg_entries(score_data)

    return score_data


def plot_score_vs_time(score_data):

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_title(f'')

    for score_name in score_names:
        selection = score_data[time_name] > 0
        scores = score_data[score_name][selection]
        times = score_data[time_name][selection]
        ax.scatter(times, scores, label=score_name)

    ax.legend(loc='upper right')
    ax.set_xlabel('days post symptom onset')
    ax.set_ylabel(score_name)
    plt.savefig(f'All_INFECT.png')


def plot_histograms(score_name, score_data, time_thresholds):

    prefix = "positive patient with "

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_title(f'')
    ax.set_yscale('log')

    negative_scores = score_data[score_name][score_data['ytrue'] == 0]

    positives = []
    pos_labels = []
    for (t_low, t_high) in time_thresholds:
        scores_per_timebin = score_data[((score_data[time_name] >= t_low) &
                                         (score_data[time_name] <= t_high))]
        if len(scores_per_timebin) > 0:
            positives.append(scores_per_timebin[score_name].dropna())
            pos_labels.append(prefix + " " + get_time_label(t_low, t_high))

    scores_outside_of_timebin = score_data[score_data['ytrue'] == 1 & score_data[time_name].isnull()]
    if len(scores_per_timebin) > 0:
        positives.append(scores_outside_of_timebin[score_name].dropna())
        pos_labels.append(f"{prefix} unknown infection time")

    ax.hist(positives, bins, alpha=1., label=pos_labels, stacked=True)
    ax.hist(negative_scores, bins, alpha=1., label='control', ec='0.', fc='none', histtype='step', lw=3)

    # tweak the axis labels
    xlab = ax.xaxis.get_label()
    ylab = ax.yaxis.get_label()

    xlab.set_style('italic')
    xlab.set_size(14)
    ylab.set_style('italic')
    ylab.set_size(14)

    # tweak the title
    ttl = ax.title
    ttl.set_weight('bold')
    ttl.set_size(20)

    ax.set_ylabel('Patients')
    ax.set_xlabel(f"r({score_name[:3]})")

    ax.legend(loc='upper right')
    plt.savefig(f'{score_name[:4]}_HIST.png')


def compute_roc(ytrue, scores):
    fpr, tpr, threshold = metrics.roc_curve(ytrue, scores)
    roc_auc = metrics.auc(fpr, tpr)
    return fpr, tpr, threshold, roc_auc


def plot_roc_curve(fpr, tpr, roc_auc, ax, label):
    p = ax.plot(fpr, tpr, label=f'{label} (AUC = {roc_auc:0.2f})', linewidth=2.)
    return p[0].get_color()


def get_optimal_thresholds(fpr, tpr, threshold, cost_ratios):

    optimal_thresholds = {}

    for cr in cost_ratios:
        m = ((1 - prior_probability_of_disease) / prior_probability_of_disease) * cr
        utility = tpr - m * (fpr)
        best_th_index = np.argmax(utility)
        optimal_thresholds[cr] = (threshold[best_th_index])
        optimal_thresholds[cr] = (threshold[best_th_index], tpr[best_th_index], fpr[best_th_index])

    return optimal_thresholds


def plot_thresholds(optimal_thresholds, colors, ax):
    for k in optimal_thresholds:
        for cr, (th, tpr_at_th, fpr_at_th) in optimal_thresholds[k].items():
            # find point on curve closest to optimal threshold
            ax.scatter(fpr_at_th, tpr_at_th,
                       marker=cr2marker[cr],
                       color=colors[k],
                       label=f"{k}\noptimal threshold $r^*={th:0.2f}$ for m = {cr}",
                       # label=f"optimal threshold {opt_th} \nfor (false positive cost) / (false negative cost) = {cr}",
                       s=100.,
                       zorder=1000)

def plot_roc(score_data, score_name, time_thresholds, cost_ratios):

    optimal_thresholds = {}
    colors = {}

    roc_data = score_data[['ytrue', score_name]].dropna()

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_title(f'Receiver Operating Characteristic for {score_name[:3]}')

    fpr, tpr, threshold, roc_auc = compute_roc(roc_data['ytrue'], roc_data[score_name])
    color = plot_roc_curve(fpr, tpr, roc_auc, ax, "all patients")
    optimal_thresholds["all patients"] = get_optimal_thresholds(fpr,
                                                                tpr,
                                                                threshold,
                                                                cost_ratios)
    colors["all patients"] = color

    for (t_low, t_high) in time_thresholds:
        label = get_time_label(t_low, t_high)

        roc_data_per_timebin = score_data[['ytrue', score_name, time_name]].copy()
        roc_data_per_timebin[time_name].fillna(-1, inplace=True)
        roc_data_per_timebin.dropna(inplace=True)
        roc_data_per_timebin = roc_data_per_timebin[((roc_data_per_timebin[time_name] >= t_low) &
                                                     (roc_data_per_timebin[time_name] <= t_high)) |
                                                    (roc_data_per_timebin['ytrue'] == 0)]

        fpr, tpr, threshold, roc_auc = compute_roc(roc_data_per_timebin['ytrue'],
                                                   roc_data_per_timebin[score_name])
        color = plot_roc_curve(fpr, tpr, roc_auc, ax, label)
        colors[label] = color
        optimal_thresholds[label] = get_optimal_thresholds(fpr,
                                                           tpr,
                                                           threshold,
                                                           cost_ratios)

    plot_thresholds(optimal_thresholds, colors, ax)

    # tweak the axis labels
    xlab = ax.xaxis.get_label()
    ylab = ax.yaxis.get_label()

    xlab.set_style('italic')
    xlab.set_size(14)
    ylab.set_style('italic')
    ylab.set_size(14)

    # tweak the title
    ttl = ax.title
    ttl.set_weight('bold')
    ttl.set_size(16)

    ax.legend(loc='lower right')
    plt.plot([0, 1], [0, 1], 'r--')
    ax.set_xlim([-0.05, 1.])
    ax.set_ylim([0., 1.05])
    ax.set_ylabel('True Positive Rate')
    ax.set_xlabel('False Positive Rate')
    plt.savefig(f'{score_name[:4]}_ROC.png')

score_data = parse_csv(analysis_file, score_names)
score_data.to_csv('used_data.csv', index=False)

plot_score_vs_time(score_data)
for score_name in score_names:
    plot_histograms(score_name, score_data, time_thresholds)

    plot_roc(score_data,
             score_name,
             time_thresholds=time_thresholds_roc,
             cost_ratios=cost_ratios)
