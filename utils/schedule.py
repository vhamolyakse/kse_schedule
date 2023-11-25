import pandas as pd
from .time_utils import get_timeslot_list

class ScheduleManager:

    def __init__(self, optapy_solution=None, raw_schedule_df=None):
        if optapy_solution != None:
            self.raw_schedule_df = self._parse_optapy_solution(optapy_solution)
        else:
            self.raw_schedule_df = raw_schedule_df
    
    def _parse_optapy_solution(self, solution):
        scheduling_records_data = []
        for num, l in enumerate(solution.get_lesson_list()):
            scheduling_records_data.append({
                'room': f"{l.room.name} [{l.room.capacity}]" ,
                'student_group': f"{l.student_group.name}", # [{l.student_group_capacity}]",
                'subject': l.subject,
                'teacher': ' '.join(l.teacher.name.split(' ')[:2]),
                'day': l.timeslot.day_of_week,
                'start_time': l.timeslot.start_time,
                'lesson_id': l.id,
                'room_id': l.room.id,
                'time_slot_id': l.timeslot.id,
                'schedule_id': num
            })

        raw_schedule_df = pd.DataFrame(scheduling_records_data)
        return raw_schedule_df
    
    def raw_schedule_to_pretty(self, raw_schedule_df):
        raw_schedule_df['text'] = raw_schedule_df.apply(lambda row: f"{row['subject']}\n{row['student_group']}\n{row['teacher']}\n[{row['schedule_id']}]", axis=1)
        pivot_df = raw_schedule_df.pivot(index=['day', 'start_time'], columns='room', values='text')

        df = pivot_df.fillna('').copy()
        df = df.reset_index()
        days_order = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']
        df['day_int'] = df['day'].apply(lambda d: days_order.index(d))
        df.sort_values(by=['day_int', 'start_time'], inplace=True)
        df.drop('day_int', axis=1, inplace=True)

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
        return df