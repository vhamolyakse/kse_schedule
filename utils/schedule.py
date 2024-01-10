import pandas as pd
import numpy as np
from datetime import timedelta, datetime
import json
# from pandas import json_normalize
# from .time_utils import get_timeslot_list


def _get_pair_number(start_time_str):
    pair_times = [
        ('08:30', '09:50', 1),
        ('10:00', '11:20', 2),
        ('11:30', '12:50', 3),
        ('13:30', '14:50', 4),
        ('15:00', '16:20', 5),
        ('16:30', '17:50', 6),
        ('18:00', '19:20', 7),
        ('19:30', '20:50', 8)
    ]

    formatted_start_time = str(start_time_str).strip()[:5]

    start_time = datetime.strptime(formatted_start_time, '%H:%M')

    for start, end, pair_number in pair_times:
        start_dt = datetime.strptime(start, '%H:%M')
        end_dt = datetime.strptime(end, '%H:%M')
        if start_dt <= start_time < end_dt:
            return pair_number

    return None


class ScheduleManager:

    def __init__(self, optapy_solution=None, raw_schedule_df=None, start_date=None):
        self.start_date = start_date
        self.id_shed = 2
        if optapy_solution is not None:
            self.raw_schedule_df = self._parse_optapy_solution(optapy_solution)
        else:
            self.raw_schedule_df = raw_schedule_df

    def _parse_optapy_solution(self, solution):
        day_map = {
            'MONDAY': 1,
            'TUESDAY': 2,
            'WEDNESDAY': 3,
            'THURSDAY': 4,
            'FRIDAY': 5,
            'SATURDAY': 6,
            'SUNDAY': 7
        }
        scheduling_records_data = []
        for num, l in enumerate(solution.get_lesson_list()):
            day_of_week = day_map.get(l.timeslot.day_of_week.upper(), 0)
            lesson_date = self.start_date + timedelta(days=day_of_week)

            scheduling_records_data.append({
                'room': f"{l.room.name} [{l.room.capacity}]",
                'student_group': f"{l.student_group.name}",
                'student_group_id': l.student_group.group_id,
                # [{l.student_group_capacity}]",
                'div': 6,
                'subject': l.subject,
                'teacher': ' '.join(l.teacher.name.split(' ')[:2]),
                'day': l.timeslot.day_of_week,
                'day_of_week': day_of_week,
                'lesson_date': lesson_date,
                'start_time': l.timeslot.start_time,
                'num_pair': _get_pair_number(l.timeslot.start_time),
                'lesson_id': l.id,
                'lesson_kse_id': l.lesson_id,
                'is_online': l.is_online,
                'room_id': l.room.id,
                'auditory_id': l.room.auditory_id,
                'time_slot_id': l.timeslot.id,
                'schedule_id': num,
                'teacher_id': l.teacher_id,
                'is_lection': l.is_lection
            })
        # import pdb
        # pdb.set_trace()
        raw_schedule_df = pd.DataFrame(scheduling_records_data)
        return raw_schedule_df

    def create_json_from_df(self, raw_schedule_df):
        # print(raw_schedule_df['student_group_id'])
        if not pd.api.types.is_datetime64_any_dtype(raw_schedule_df['lesson_date']):
            raw_schedule_df['lesson_date'] = pd.to_datetime(raw_schedule_df['lesson_date'])

        raw_schedule_df['lesson_date'] = raw_schedule_df['lesson_date'].dt.strftime('%Y-%m-%d')

        for col in raw_schedule_df.select_dtypes(['datetime', 'timedelta']):
            raw_schedule_df[col] = raw_schedule_df[col].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else None)

        mapping = {
            'auditory_id': 'ID_AUD',
            'div': 'ID_DIV',
            'lesson_kse_id': 'ID_DISC',
            'is_lection': 'ID_STUD',
            'teacher_id': 'ID_TEACH',
            'num_pair': 'NUM_PAIR',
            'lesson_date': 'DATE_PAIR',
            'student_group_id': 'GROUPS'

        }

        df_mapped = raw_schedule_df.rename(columns=mapping)

        df_mapped1 = df_mapped[['ID_AUD', 'ID_DIV']]
        df_mapped1['ID_SHED'] = self.id_shed
        df_mapped2 = df_mapped[['ID_DISC', 'ID_STUD', 'ID_TEACH', 'NUM_PAIR', 'DATE_PAIR', 'GROUPS']]
        df_mapped = pd.concat([df_mapped1, df_mapped2], axis=1, join='outer')

        df_mapped['ID_STUD'] = df_mapped['ID_STUD'].replace({0: 2})
        df_mapped['GROUPS'] = df_mapped['GROUPS'].apply(lambda x: [x])

        print(df_mapped)
        json_data = df_mapped.to_json(orient='records')
        # json_data = json.dumps(records, indent=2)

        return json_data


    def raw_schedule_to_pretty(self, raw_schedule_df):
        raw_schedule_df['is_lection_str'] = np.where(raw_schedule_df['is_lection'] == 1,
                                                             'лекція',
                                                             'практика')
        raw_schedule_df['is_online_str'] = np.where(raw_schedule_df['is_online'] == 1,
                                                 'онлайн',
                                                 'офлайн')
        raw_schedule_df['text'] = raw_schedule_df.apply(
            lambda row: f"{row['subject']}\n{row['student_group']}\n{row['teacher']}\n{row['is_lection_str']}\n{row['is_online_str']}\n[{row['schedule_id']}]", axis=1)
        # print(raw_schedule_df.columns)
        # print(raw_schedule_df[['day', 'start_time', 'day_of_week', 'num_pair', 'teacher_id', 'is_lection']])
        # print(raw_schedule_df['start_time'].dtype)

        raw_schedule_df['dup_id'] = raw_schedule_df.groupby(['day', 'start_time', 'room']).cumcount()
        pivot_df = raw_schedule_df.set_index(['day', 'start_time', 'room', 'dup_id']).unstack(['room', 'dup_id'])

        # raw_schedule_df = raw_schedule_df.drop_duplicates(['day', 'start_time', 'room'])
        # print(raw_schedule_df.room.unique())

        pivot_df.columns = [' '.join(map(str, col)).strip() for col in pivot_df.columns.values]
        pivot_df = pivot_df.reset_index()
        # pivot_df = raw_schedule_df.pivot(index=['day', 'start_time'], columns='room', values='text')


        # df = pivot_df.fillna('').copy()
        # df = df.reset_index()
        # days_order = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']
        # df['day_int'] = df['day'].apply(lambda d: days_order.index(d))
        # df.sort_values(by=['day_int', 'start_time'], inplace=True)
        # df.drop('day_int', axis=1, inplace=True)

        days_order = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']
        pivot_df['day_int'] = pivot_df['day'].apply(lambda d: days_order.index(d))
        pivot_df.sort_values(by=['day_int', 'start_time'], inplace=True)
        pivot_df.drop(['day_int'], axis=1, inplace=True)
        columns_to_keep = [col for col in pivot_df.columns if 'text' in col or col in ['day', 'start_time']]
        pivot_df = pivot_df[columns_to_keep]
        print(pivot_df.columns)

        # raw_schedule_df['text'] = raw_schedule_df.apply(lambda row: f"{row['subject']}\n{row['student_group']}\n{row['teacher']}\n[{row['schedule_id']}]", axis=1)

        # unique_rooms = raw_schedule_df['room'].unique()

        # # Convert start_time to a string format for MultiIndex compatibility
        # raw_schedule_df['start_time'] = raw_schedule_df['start_time'].apply(lambda t: t.strftime('%H:%M'))

        # # Create a pivot table with 'day' and 'start_time' as index, rooms as columns, using 'text' for values
        # pivot_df = raw_schedule_df.pivot(index=['day', 'start_time'], columns='room', values='text')

        # pivot_df.columns = unique_rooms
        # df = pivot_df.copy()
        # df = df.fillna('')
        # df = df.reset_index()

        # days_order = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']
        # df['day_int'] = df['day'].apply(lambda d: days_order.index(d))
        # df.sort_values(by=['day_int', 'start_time'], inplace=True)
        # df.drop('day_int', axis=1, inplace=True)
        return pivot_df.fillna('')  # df
