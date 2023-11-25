import re
import pandas as pd
import numpy as np
from .preprocessing import strip_whitespace, get_group_intersections
from .time_utils import get_teacher_availability, get_timeslot_list
from loguru import logger
from .entities import Lesson, Room, Timeslot, TimeTable, StudentGroup, Teacher


class DataManager:
    def __init__(self, data_path, existing_schedule_df=None):
        self.input_audiences_df = pd.read_csv(f'{data_path}/audiences.csv').map(strip_whitespace)
        self.input_groups_df = pd.read_csv(f'{data_path}/groups.csv').map(strip_whitespace)
        self.input_students_df = pd.read_csv(f'{data_path}/students.csv').map(strip_whitespace)
        self.input_lessons_df = pd.read_csv(f'{data_path}/lessons.csv').map(strip_whitespace)
        self.input_teachers_df = pd.read_csv(f'{data_path}/teachers.csv')    
    
        self.group_to_pupils = {}
        self.group_to_id = {}
        self.group_intersection = {}
        self.teachers_availability = None
        self.existing_schedule_df = existing_schedule_df
        self.existing_schedule_records = {}

        self.preprocessing()

        if type(self.existing_schedule_df) == pd.DataFrame:
            self.processexisting_schedule()

    def processexisting_schedule(self):
        for _, row in self.existing_schedule_df.iterrows():
            self.existing_schedule_records[row['lesson_id']] = {
                'time_slot_id': row['time_slot_id'],
                'room_id': row['room_id']
            }
            

    def preprocessing(self):
        self._preprocess_audiences()
        self._preprocess_teachers()
        self._preprocess_groups()
        self._preprocess_students()
        self._preprocess_lessons()
        
        

    def _preprocess_audiences(self):
        self.input_audiences_df = self.input_audiences_df[~pd.isna(self.input_audiences_df['is_shelter_id'])].copy()
        self.input_audiences_df.loc[:, 'name'] = self.input_audiences_df.apply(lambda row: f"{row['id']}_{row['name']}", axis=1)
        self.input_audiences_df = self.input_audiences_df.rename(columns={'id': 'kse_id'})
        self.input_audiences_df['id'] = np.arange(self.input_audiences_df.shape[0])
        self.input_audiences_df['capacity'] = self.input_audiences_df.apply(lambda row: row['capacity'] + 50 if row['name'] == '1003_TA Ventures Classroom' else row['capacity'], axis=1)
        self.input_audiences_df['capacity'] = self.input_audiences_df['capacity'] + 10  # we just need more space :)


    def _preprocess_students(self):
        self.input_students_df['id'] = np.arange(self.input_students_df.shape[0])

        for c in self.input_students_df.columns[3:]:
            self.input_students_df[c] = self.input_students_df[c].astype(str).str.strip()

        self.input_students_df = self.input_students_df.replace('nan', np.nan)
        self.input_students_df['name'] = self.input_students_df['Прізвище'] + ' ' +  self.input_students_df["Ім'я"]

    def _preprocess_groups(self):
        self.group_intersection = get_group_intersections(self.input_students_df)

        for subject in self.input_students_df.columns[3:]:
            d = self.input_students_df[subject].value_counts().to_dict()
            d = {k.rstrip().lstrip(): v for k, v in d.items()}
            self.group_to_pupils.update(d)

        self.group_to_id = {k: num for num, (k,v) in enumerate(self.group_to_pupils.items())}

    def _preprocess_lessons(self):
        # TODO: add support of online lections
        self.input_lessons_df = self.input_lessons_df[self.input_lessons_df['format'] == 'офлайн']
        self.input_lessons_df['count'] = self.input_lessons_df['count'].astype(int)
        duplicated_rows = pd.DataFrame(self.input_lessons_df.loc[self.input_lessons_df.index.repeat(self.input_lessons_df['count'])].reset_index(drop=True))
        duplicated_rows.drop('count', axis=1, inplace=True)
        self.input_lessons_df = duplicated_rows.copy()
        self.input_lessons_df['id'] = np.arange(self.input_lessons_df.shape[0])


        self.input_lessons_df['pupils'] = self.input_lessons_df['group'].apply(lambda v: self.group_to_pupils.get(v, -1))
        logger.debug(f'Before filtering lessons count: {self.input_lessons_df.shape[0]}')
        logger.warning(f"This groups doesnt have pupils: {self.input_lessons_df[self.input_lessons_df['pupils'] == -1]['group'].values.tolist()}")
        self.input_lessons_df = self.input_lessons_df[self.input_lessons_df['pupils'] != - 1]
        logger.debug(f'After filtering lessons count: {self.input_lessons_df.shape[0]}')
        

    def _preprocess_teachers(self):
        timeslot_list = get_timeslot_list()
        timeslot_dict = {day: [] for day in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']}
        for timeslot in timeslot_list:
            timeslot_dict[timeslot.day_of_week].append(timeslot)
            
        self.input_teachers_df['name'] = self.input_teachers_df['name'].apply(lambda v: v.rstrip().lstrip())
        self.input_teachers_df = self.input_teachers_df.replace('online ', 1).fillna(1)
        self.teachers_availability = get_teacher_availability(self.input_teachers_df, timeslot_dict)


    def generate_optapy_problem(self, reschedule_lesson_id=None, forbidden_time_slots=None):
        timeslot_list = get_timeslot_list()

        room_list = []
        for _, row in self.input_audiences_df.iterrows():
            room_list.append(Room(row['id'], row['name'], row['capacity']))

        group_objects = {}
        for group_name, pupils in self.group_to_pupils.items():
            group_id = self.group_to_id[group_name]
            group_objects[group_name] = StudentGroup(group_id, group_name, pupils)


        lesson_list = []

        for num, (_, row) in enumerate(self.input_lessons_df.iterrows()):
            try:
                students_df = self.input_students_df[self.input_students_df[row['subject'].strip()] ==  row['group']].copy()

                group = group_objects[row['group']] #StudentGroup(group_to_id[row['group']], row['group'], students_df.shape[0])
                
                if num == reschedule_lesson_id:
                    #print('reschedule_lesson_id', reschedule_lesson_id)
                    lesson = Lesson(row['id'], row['subject'], 
                                    Teacher(row['teacher'], self.teachers_availability[row['teacher']]),
                                    group, students_df.shape[0], group_intersection=self.group_intersection,
                                    forbidden_timeslots={int(k): int(v) for k, v in forbidden_time_slots.items()}, is_fixed=False)

                elif row['id'] in self.existing_schedule_records:
                    #print('in existing_schedule_records', num)
                    ideal_time_slot_id = self.existing_schedule_records[row['id']]['time_slot_id']
                    ideal_room_id = self.existing_schedule_records[row['id']]['room_id']
                    lesson = Lesson(row['id'], row['subject'],
                            Teacher(row['teacher'], self.teachers_availability[row['teacher']]),
                            group, students_df.shape[0], group_intersection=self.group_intersection, 
                            ideal_room_id=ideal_room_id, ideal_timeslot_id=ideal_time_slot_id, is_fixed=True)

                else:
                    lesson = Lesson(row['id'], row['subject'],
                                    Teacher(row['teacher'], self.teachers_availability[row['teacher']]),
                                    group, students_df.shape[0], group_intersection=self.group_intersection)
                #print(lesson)
                lesson_list.append(lesson)
            except Exception as e:
                print('exception', e)

        lesson = lesson_list[0]
        lesson.is_pinned = True
        lesson.set_timeslot(timeslot_list[0])
        lesson.set_room(room_list[0])
        
        lesson_list[0] = lesson
        return TimeTable(timeslot_list, room_list, lesson_list)

if __name__ == '__main__':
    data_manager = DataManager('uploaded_files')
    

    import pdb
    from constraints import define_constraints, get_solver_config
    from optapy import solver_factory_create, score_manager_create

    problem = data_manager.generate_optapy_problem()
    solver_config = get_solver_config()
    solver_factory = solver_factory_create(solver_config)
    solver = solver_factory.buildSolver()
    solution = solver.solve(problem)
    score_manager = score_manager_create(solver_factory)
    explanation = score_manager.explainScore(solution)

    logger.debug(f"Final score: {str(solution.get_score())}")
    logger.debug(f"Score explenation: {str(explanation)}")

