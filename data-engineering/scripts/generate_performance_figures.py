import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

CLI_DESC = """
Elyssa-IMDb: regenerate the 12 pipeline performance figures
(Docs figures, tracked for the public repository).

Usage:
    python generate_performance_figures.py [output_dir]

Default output: <repo>/data-engineering/docs/figures
"""

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'figures')
os.makedirs(OUT, exist_ok=True)

# ============================================================
# UNIFIED STYLE
# ============================================================
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 150,
    'savefig.dpi': 150,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.edgecolor': '#555',
    'axes.linewidth': 0.6,
    'ytick.major.width': 0.4,
    'xtick.major.width': 0.4,
})

EDGE = '#555'
LW = 0.6
ANNO_FS = 9
TITLE_FS = 12
LABEL_FS = 10
TICK_FS = 9

# ============================================================
# DATA
# ============================================================
bronze_rows = {
    'title_basics': 12686436, 'title_akas': 58762567, 'title_episode': 9808098,
    'title_principals': 100989556, 'title_ratings': 1701910, 'name_basics': 15542711,
    'title_crew': 12687304,
}
silver_rows = {
    'title_basics': 12686436, 'title_akas': 58762567, 'title_episode': 9808096,
    'title_principal': 100989556, 'title_rating': 1701910, 'name_basics': 15542622,
    'title_genre': 19769295, 'title_director': 9449756, 'title_writer': 15004156,
    'title_akas_type': 19373706, 'title_akas_attribute': 313178,
    'title_principal_char': 49239683, 'name_profession': 17270638,
    'name_known_for_title': 25181575,
}
gold_rows = {
    'dim_person': 15542622, 'dim_title': 12407870, 'fact_episode': 9808096,
    'fact_performance': 100989562, 'fact_title_principal': 100989556,
    'fact_title_rating': 1701910,
}
containers = ['elyssa-airflow', 'elyssa-postgres', 'elyssa-rustfs']
mem_gb = [1.126, 0.102, 0.070]
mem_limit = [2.5, 2.0, 0.256]
mem_pct = [45.05, 5.10, 28.00]
cpu_pct = [11.84, 4.19, 0.04]
net_in = [62.3, 82.9, 0.012]
net_out = [82.9, 62.3, 0.003]
silver_export_times = {
    'title_principal': 351, 'title_akas': 239, 'title_basics': 140,
    'name_basics': 115, 'title_principal_char': 107, 'name_known_for_title': 53,
    'title_akas_type': 35, 'name_profession': 32, 'title_director': 34,
    'title_writer': 31, 'title_genre': 30, 'title_episode': 29,
    'title_rating': 6, 'title_akas_attribute': 1,
}
gold_export_times = {
    'fact_title_principal': 436, 'fact_performance': 390, 'dim_title': 180,
    'dim_person': 76, 'fact_episode': 53, 'fact_title_rating': 4,
}
cross_layer = {
    'title.basics': {'silver': 'title_basics', 'gold': 'dim_title'},
    'name.basics': {'silver': 'name_basics', 'gold': 'dim_person'},
    'title.episode': {'silver': 'title_episode', 'gold': 'fact_episode'},
    'title.principals': {'silver': 'title_principal', 'gold': 'fact_title_principal'},
    'title.ratings': {'silver': 'title_rating', 'gold': 'fact_title_rating'},
}
bronze_key_map = {
    'title.basics': 'title_basics', 'name.basics': 'name_basics',
    'title.episode': 'title_episode', 'title.principals': 'title_principals',
    'title.ratings': 'title_ratings',
}


def fmt_dur(sec):
    h, m, s = int(sec // 3600), int((sec % 3600) // 60), sec % 60
    if h:
        return f'{h}h {m}m {s:.0f}s'
    if m:
        return f'{m}m {s:.0f}s'
    return f'{s:.0f}s'


# ============================================================
# CHART 1: Layer Duration Breakdown
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5))
labels = ['Bronze', 'Silver', 'Gold']
durations = [12, 1217, 25361]
colors = ['#CD7F32', '#C0C0C0', '#FFD700']
bars = ax.barh(labels, durations, color=colors, edgecolor=EDGE, linewidth=LW)
for bar, dur in zip(bars, durations):
    ax.text(bar.get_width() + 300, bar.get_y() + bar.get_height() / 2,
            fmt_dur(dur), va='center', fontsize=ANNO_FS)
ax.set_xlabel('Duration (seconds)', fontsize=LABEL_FS)
ax.set_title('Pipeline Duration by Layer', fontsize=TITLE_FS)
ax.set_xlim(0, max(durations) * 1.15)
plt.tight_layout()
plt.savefig(f'{OUT}/01_layer_duration.png')
plt.close()
print('01 done')


# ============================================================
# CHART 2: Gold Sub-Phase Breakdown
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5))
sub_labels = ['dbt run', 'dbt test', 'DQ checks', 'Freshness', 'Gold export']
sub_durs = [10721, 3527, 231, 118, 1146]
sub_colors = ['#4472C4', '#5B9BD5', '#ED7D31', '#FFC000', '#70AD47']
bars = ax.barh(sub_labels, sub_durs, color=sub_colors, edgecolor=EDGE, linewidth=LW)
for bar, dur in zip(bars, sub_durs):
    ax.text(bar.get_width() + 100, bar.get_y() + bar.get_height() / 2,
            fmt_dur(dur), va='center', fontsize=ANNO_FS)
ax.set_xlabel('Duration (seconds)', fontsize=LABEL_FS)
ax.set_title('Gold Layer Sub-Phase Breakdown', fontsize=TITLE_FS)
ax.set_xlim(0, max(sub_durs) * 1.18)
plt.tight_layout()
plt.savefig(f'{OUT}/02_gold_subphases.png')
plt.close()
print('02 done')


# ============================================================
# CHART 3: Row Counts per Table
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=False)

b_names = list(bronze_rows.keys())
b_vals = [v / 1e6 for v in bronze_rows.values()]
axes[0].barh(b_names, b_vals, color='#CD7F32', edgecolor=EDGE, linewidth=LW)
axes[0].set_title('Bronze (7 tables)', fontsize=TITLE_FS)
axes[0].set_xlabel('Rows (millions)', fontsize=LABEL_FS)
for i, v in enumerate(b_vals):
    axes[0].text(v + 0.5, i, f'{v:.1f}M', va='center', fontsize=TICK_FS)

s_sorted = sorted(silver_rows.items(), key=lambda x: x[1], reverse=True)[:8]
s_names = [x[0] for x in s_sorted]
s_vals = [x[1] / 1e6 for x in s_sorted]
axes[1].barh(s_names, s_vals, color='#C0C0C0', edgecolor=EDGE, linewidth=LW)
axes[1].set_title('Silver (top 8 of 14)', fontsize=TITLE_FS)
axes[1].set_xlabel('Rows (millions)', fontsize=LABEL_FS)
for i, v in enumerate(s_vals):
    axes[1].text(v + 0.5, i, f'{v:.1f}M', va='center', fontsize=TICK_FS)

g_names = list(gold_rows.keys())
g_vals = [v / 1e6 for v in gold_rows.values()]
axes[2].barh(g_names, g_vals, color='#FFD700', edgecolor=EDGE, linewidth=LW)
axes[2].set_title('Gold (6 tables)', fontsize=TITLE_FS)
axes[2].set_xlabel('Rows (millions)', fontsize=LABEL_FS)
for i, v in enumerate(g_vals):
    axes[2].text(v + 0.5, i, f'{v:.1f}M', va='center', fontsize=TICK_FS)

fig.suptitle('Row Counts by Layer', fontsize=TITLE_FS + 1, y=1.02)
plt.tight_layout()
plt.savefig(f'{OUT}/03_row_counts.png')
plt.close()
print('03 done')


# ============================================================
# CHART 4: Disk Volume Growth
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))
layers = ['Bronze\nParquet', 'Silver\nParquet', 'Gold\nParquet', 'PostgreSQL\n(total)']
sizes_gb = [2.64, 4.48, 5.7, 97]
colors = ['#CD7F32', '#C0C0C0', '#FFD700', '#4472C4']
bars = ax.bar(layers, sizes_gb, color=colors, edgecolor=EDGE, linewidth=LW, width=0.6)
for bar, sz in zip(bars, sizes_gb):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
            f'{sz:.1f} GB', ha='center', va='bottom', fontsize=ANNO_FS)
ax.set_ylabel('Size (GB)', fontsize=LABEL_FS)
ax.set_title('Data Volume by Layer', fontsize=TITLE_FS)
plt.tight_layout()
plt.savefig(f'{OUT}/04_disk_volume.png')
plt.close()
print('04 done')


# ============================================================
# CHART 5: Cross-Layer Ratios
# ============================================================
fig, ax = plt.subplots(figsize=(12, 5))
x_labels = list(cross_layer.keys())
bronze_vals = [bronze_rows[bronze_key_map[k]] / 1e6 for k in x_labels]
silver_vals = [silver_rows[cross_layer[k]['silver']] / 1e6 for k in x_labels]
gold_vals = [gold_rows[cross_layer[k]['gold']] / 1e6 for k in x_labels]

x = np.arange(len(x_labels))
w = 0.25
ax.bar(x - w, bronze_vals, w, label='Bronze', color='#CD7F32', edgecolor=EDGE, linewidth=LW)
ax.bar(x, silver_vals, w, label='Silver', color='#C0C0C0', edgecolor=EDGE, linewidth=LW)
ax.bar(x + w, gold_vals, w, label='Gold', color='#FFD700', edgecolor=EDGE, linewidth=LW)

ax.set_ylabel('Rows (millions)', fontsize=LABEL_FS)
ax.set_title('Cross-Layer Row Count Ratios', fontsize=TITLE_FS)
ax.set_xticks(x)
ax.set_xticklabels(x_labels, rotation=20, ha='right', fontsize=TICK_FS)
ax.legend(fontsize=TICK_FS)
plt.tight_layout()
plt.savefig(f'{OUT}/05_cross_layer_ratios.png')
plt.close()
print('05 done')


# ============================================================
# CHART 6: Container Resource Usage
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
x = np.arange(len(containers))

# Memory
axes[0].bar(x, mem_gb, 0.5, label='Used', color=['#4472C4', '#ED7D31', '#70AD47'], edgecolor=EDGE, linewidth=LW)
axes[0].bar(x, [lim - u for lim, u in zip(mem_limit, mem_gb)], 0.5, bottom=mem_gb,
            label='Free', color=['#BDD7EE', '#F8CBAD', '#C6EFCE'], edgecolor=EDGE, linewidth=LW, alpha=0.5)
axes[0].set_xticks(x)
axes[0].set_xticklabels(containers, rotation=15, ha='right', fontsize=TICK_FS)
axes[0].set_ylabel('Memory (GB)', fontsize=LABEL_FS)
axes[0].set_title('Memory Usage vs Limit', fontsize=TITLE_FS)
axes[0].legend(fontsize=TICK_FS)
for i, (u, lim) in enumerate(zip(mem_gb, mem_limit)):
    axes[0].text(i, lim + 0.03, f'{u:.2f}/{lim:.1f} GB\n({mem_pct[i]:.0f}%)',
                 ha='center', va='bottom', fontsize=8)
axes[0].set_ylim(0, max(mem_limit) * 1.25)

# CPU
axes[1].bar(x, cpu_pct, 0.5, color=['#4472C4', '#ED7D31', '#70AD47'], edgecolor=EDGE, linewidth=LW)
axes[1].set_xticks(x)
axes[1].set_xticklabels(containers, rotation=15, ha='right', fontsize=TICK_FS)
axes[1].set_ylabel('CPU (%)', fontsize=LABEL_FS)
axes[1].set_title('CPU Utilization', fontsize=TITLE_FS)
for i, c in enumerate(cpu_pct):
    axes[1].text(i, c + 0.5, f'{c:.1f}%', ha='center', va='bottom', fontsize=ANNO_FS)

plt.tight_layout()
plt.savefig(f'{OUT}/06_container_resources.png')
plt.close()
print('06 done')


# ============================================================
# CHART 7: Silver Export Per-Table Timing
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6))
s_sorted = sorted(silver_export_times.items(), key=lambda x: x[1], reverse=True)
s_names = [x[0] for x in s_sorted]
s_times = [x[1] for x in s_sorted]
colors_s = plt.cm.Greys(np.linspace(0.3, 0.8, len(s_names)))
ax.barh(s_names, s_times, color=colors_s, edgecolor=EDGE, linewidth=LW)
for i, t in enumerate(s_times):
    m, s = divmod(t, 60)
    txt = f'{m}m {s}s' if m else f'{s}s'
    ax.text(t + 3, i, txt, va='center', fontsize=ANNO_FS)
ax.set_xlabel('Duration (seconds)', fontsize=LABEL_FS)
ax.set_title('Silver Export: Per-Table Duration', fontsize=TITLE_FS)
ax.set_xlim(0, max(s_times) * 1.2)
plt.tight_layout()
plt.savefig(f'{OUT}/07_silver_export_timing.png')
plt.close()
print('07 done')


# ============================================================
# CHART 8: Gold Export Per-Table Timing
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5))
g_sorted = sorted(gold_export_times.items(), key=lambda x: x[1], reverse=True)
g_names = [x[0] for x in g_sorted]
g_times = [x[1] for x in g_sorted]
colors_g = ['#FFD700', '#DAA520', '#B8860B', '#CD853F', '#DEB887', '#F5DEB3']
ax.barh(g_names, g_times, color=colors_g[:len(g_names)], edgecolor=EDGE, linewidth=LW)
for i, t in enumerate(g_times):
    m, s = divmod(t, 60)
    txt = f'{m}m {s}s' if m else f'{s}s'
    ax.text(t + 5, i, txt, va='center', fontsize=ANNO_FS)
ax.set_xlabel('Duration (seconds)', fontsize=LABEL_FS)
ax.set_title('Gold Export: Per-Table Duration', fontsize=TITLE_FS)
ax.set_xlim(0, max(g_times) * 1.18)
plt.tight_layout()
plt.savefig(f'{OUT}/08_gold_export_timing.png')
plt.close()
print('08 done')


# ============================================================
# CHART 9: Throughput
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))
tp_labels = ['Bronze\n(ingestion)', 'Silver\n(export)', 'Gold\n(dbt run)', 'Gold\n(export)']
tp_rows = [212178582, 355093174, 241439616, 241439616]
tp_secs = [2.8, 1212, 10719, 1139]
tp_rps = [r / s for r, s in zip(tp_rows, tp_secs)]
tp_colors = ['#CD7F32', '#C0C0C0', '#4472C4', '#FFD700']
bars = ax.bar(tp_labels, tp_rps, color=tp_colors, edgecolor=EDGE, linewidth=LW, width=0.5)
for bar, rps in zip(bars, tp_rps):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5000,
            f'{rps:,.0f} r/s', ha='center', va='bottom', fontsize=ANNO_FS)
ax.set_ylabel('Rows / Second', fontsize=LABEL_FS)
ax.set_title('Data Throughput by Operation', fontsize=TITLE_FS)
plt.tight_layout()
plt.savefig(f'{OUT}/09_throughput.png')
plt.close()
print('09 done')


# ============================================================
# CHART 10: Network I/O
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(len(containers))
w = 0.3
ax.bar(x - w / 2, net_in, w, label='Inbound', color='#4472C4', edgecolor=EDGE, linewidth=LW)
ax.bar(x + w / 2, net_out, w, label='Outbound', color='#ED7D31', edgecolor=EDGE, linewidth=LW)
ax.set_xticks(x)
ax.set_xticklabels(containers, rotation=15, ha='right', fontsize=TICK_FS)
ax.set_ylabel('Data (MB)', fontsize=LABEL_FS)
ax.set_title('Network I/O by Container', fontsize=TITLE_FS)
ax.legend(fontsize=TICK_FS)
plt.tight_layout()
plt.savefig(f'{OUT}/10_network_io.png')
plt.close()
print('10 done')


# ============================================================
# CHART 11: ETL Correctness + Intrinsic Quality
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Left: Row count comparison
bronze_tables = ['title_basics', 'name_basics', 'title_principals', 'title_episode']
bronze_rc = [12686436, 15542711, 100989556, 9808098]
gold_rc = [12407870, 15542622, 100989556, 9808096]
x = np.arange(len(bronze_tables))
w = 0.35
axes[0].bar(x - w / 2, [r / 1e6 for r in bronze_rc], w, label='Bronze', color='#CD7F32', edgecolor=EDGE, linewidth=LW)
axes[0].bar(x + w / 2, [r / 1e6 for r in gold_rc], w, label='Gold', color='#FFD700', edgecolor=EDGE, linewidth=LW)
axes[0].set_ylabel('Rows (millions)', fontsize=LABEL_FS)
axes[0].set_title('ETL Correctness: Bronze vs Gold', fontsize=TITLE_FS)
axes[0].set_xticks(x)
axes[0].set_xticklabels(['title_basics\n-> dim_title', 'name_basics\n-> dim_person',
                          'title_principals\n-> fact_title_principal', 'title_episode\n-> fact_episode'],
                         fontsize=TICK_FS)
axes[0].legend(fontsize=TICK_FS)
for i, (b, g) in enumerate(zip(bronze_rc, gold_rc)):
    delta = (g - b) / b * 100
    color = '#70AD47' if abs(delta) < 1 else '#ED7D31'
    axes[0].text(i, max(b, g) / 1e6 + 1, f'{delta:+.2f}%', ha='center', fontsize=ANNO_FS, color=color)

# Right: Intrinsic quality findings
checks = ['PK uniqueness\n(dim_title)', 'PK uniqueness\n(dim_person)',
          'PK uniqueness\n(fact tables)', 'Format validation',
          'Data anomalies', 'Referential\nintegrity']
status_counts = [2, 1, 4, 7, 5, 2]
colors_q = ['#70AD47', '#70AD47', '#ED7D31', '#70AD47', '#ED7D31', '#ED7D31']
bars = axes[1].barh(checks, status_counts, color=colors_q, edgecolor=EDGE, linewidth=LW)
for bar, cnt in zip(bars, status_counts):
    axes[1].text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                 f'{cnt} checks', va='center', fontsize=ANNO_FS)
axes[1].set_xlabel('Number of Checks', fontsize=LABEL_FS)
axes[1].set_title('Intrinsic Quality Findings', fontsize=TITLE_FS)
axes[1].set_xlim(0, max(status_counts) + 1.5)
legend_elements = [mpatches.Patch(facecolor='#70AD47', edgecolor=EDGE, label='PASS'),
                   mpatches.Patch(facecolor='#ED7D31', edgecolor=EDGE, label='WARN/FAIL')]
axes[1].legend(handles=legend_elements, loc='lower right', fontsize=TICK_FS)

plt.tight_layout()
plt.savefig(f'{OUT}/11_etl_correctness_quality.png')
plt.close()
print('11 done')


# ============================================================
# CHART 12: Completeness Null Rates
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# dim_title
dt_cols = ['end_year', 'average_rating', 'num_votes', 'writer_names', 'language_list',
           'director_names', 'season_number', 'episode_number', 'runtime_minutes',
           'parent_tconst', 'series_title', 'region_list', 'aka_count', 'start_year']
dt_nulls = [98.7, 86.6, 86.6, 49.6, 52.8, 44.8, 37.5, 37.5, 63.3, 21.0, 21.0, 29.6, 29.6, 11.1]
colors_dt = ['#ED7D31' if n > 80 else '#FFC000' if n > 50 else '#A5A5A5' for n in dt_nulls]
axes[0].barh(dt_cols, dt_nulls, color=colors_dt, edgecolor=EDGE, linewidth=LW)
for i, n in enumerate(dt_nulls):
    axes[0].text(n + 1, i, f'{n}%', va='center', fontsize=ANNO_FS)
axes[0].set_xlabel('Null Rate (%)', fontsize=LABEL_FS)
axes[0].set_title('dim_title: High Null-Rate Columns', fontsize=TITLE_FS)
axes[0].set_xlim(0, 110)
axes[0].axvline(x=50, color='red', linestyle='--', alpha=0.4, linewidth=0.8)

# dim_person
dp_cols = ['age_at_death', 'death_year', 'birth_year', 'generation', 'profession_list', 'known_for_titles']
dp_nulls = [98.4, 98.3, 95.6, 95.6, 20.2, 12.1]
colors_dp = ['#ED7D31' if n > 80 else '#FFC000' if n > 50 else '#A5A5A5' for n in dp_nulls]
axes[1].barh(dp_cols, dp_nulls, color=colors_dp, edgecolor=EDGE, linewidth=LW)
for i, n in enumerate(dp_nulls):
    axes[1].text(n + 1, i, f'{n}%', va='center', fontsize=ANNO_FS)
axes[1].set_xlabel('Null Rate (%)', fontsize=LABEL_FS)
axes[1].set_title('dim_person: High Null-Rate Columns', fontsize=TITLE_FS)
axes[1].set_xlim(0, 110)
axes[1].axvline(x=50, color='red', linestyle='--', alpha=0.4, linewidth=0.8)

legend_elements = [mpatches.Patch(facecolor='#ED7D31', edgecolor=EDGE, label='>80% null'),
                   mpatches.Patch(facecolor='#FFC000', edgecolor=EDGE, label='50-80% null'),
                   mpatches.Patch(facecolor='#A5A5A5', edgecolor=EDGE, label='<50% null')]
fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=TICK_FS)

plt.tight_layout()
plt.savefig(f'{OUT}/12_completeness_null_rates.png')
plt.close()
print('12 done')

print(f'\nAll 12 charts regenerated in {OUT}')
