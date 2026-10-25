"""Write comparison tables only for reports with matching evaluation conditions."""
import argparse
import csv
import json
from pathlib import Path


def comparison_key(report):
    experiment = report['experiment']
    return [experiment[key] for key in ('kind', 'environment', 'robot_count', 'dataset', 'configuration')] + [
        report['alignment']['mode'], report['association']['tolerance_s'],
        report['rpe_delta_s'], report['rpe_tolerance_s'], report['inputs']['reference']['sha256']]


def compare(paths, output):
    reports = [json.loads(Path(path).read_text(encoding='utf-8')) for path in paths]
    if len(reports) < 2:
        raise ValueError('At least two reports are required')
    if any(comparison_key(report) != comparison_key(reports[0]) for report in reports[1:]):
        raise ValueError('Evaluation conditions differ; no comparison was written')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    columns = ['algorithm', 'version', 'kind', 'matched', 'estimate_coverage', 'reference_coverage', 'ate_rmse_m', 'rpe_rmse_m']
    rows = []
    for report in reports:
        experiment, association = report['experiment'], report['association']
        rows.append([experiment['algorithm'], experiment['version'], experiment['kind'], association['matched'],
                     association['estimated_fraction'], association['reference_fraction'], report['ate_m']['rmse'],
                     report['rpe']['translation_m']['rmse'] if report['rpe'] else 'unavailable'])
    with (output / 'comparison.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    def escape(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    text = '# Trajectory comparison\n\nConditions match; coverage differences remain visible. No ranking is inferred.\n\n'
    text += '| ' + ' | '.join(columns) + ' |\n| ' + ' | '.join('---' for _ in columns) + ' |\n'
    text += ''.join('| ' + ' | '.join(map(escape, row)) + ' |\n' for row in rows)
    (output / 'comparison.md').write_text(text, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        compare(args.reports, args.output)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + '\n')
