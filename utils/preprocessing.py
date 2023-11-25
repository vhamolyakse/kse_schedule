from collections import defaultdict

def strip_whitespace(x):
    if isinstance(x, str):
        return x.lstrip().rstrip()
    return x

def get_group_intersections(students_df):
    group_intersection = defaultdict(dict)

    required_columns = [c for c in students_df.columns.values[3:].tolist() if c not in ['id', 'name']]

    for subject in required_columns:
        for group in students_df[subject].dropna().unique():
            group_df = students_df[students_df[subject] == group]
            for subject_2 in [s for s in required_columns if s != subject]:
                group_intersection[group].update({v: 1 for v in group_df[subject_2].dropna().unique()})
    return group_intersection