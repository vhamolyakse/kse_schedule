import streamlit as st
st.title('Update schedule')
st.write('Here you can update a schedule!')

import pandas as pd
import numpy as np
import os
from datetime import datetime
from optapy import problem_fact, planning_id
from optapy import solver_factory_create, score_manager_create

from utils.preprocessing import strip_whitespace, get_group_intersections
from utils.entities import StudentGroup, Teacher, Room, Timeslot, Lesson, TimeTable
from utils.time_utils import get_teacher_availability, get_timeslot_list
from collections import defaultdict
from datetime import time
from optapy import solver_factory_create, score_manager_create

from optapy import get_class
import optapy.config
from optapy.types import Duration

# from IPython.display import display, HTML

from loguru import logger
import streamlit as st
from io import StringIO



from optapy import constraint_provider, get_class
from optapy.constraint import Joiners
from optapy.score import HardSoftScore

# Constraint Factory takes Java Classes, not Python Classes
LessonClass = get_class(Lesson)
RoomClass = get_class(Room)
group_intersection = None

@constraint_provider
def define_constraints(constraint_factory):
    return [
        # Hard constraints
        room_conflict(constraint_factory),
        teacher_conflict(constraint_factory),
        student_group_conflict(constraint_factory),
        room_capacity_conflict(constraint_factory),
        teacher_availability_conflict(constraint_factory),
        student_conflict(constraint_factory),
        #penalize_lesson_not_in_ideal_timeslot(constraint_factory),
        #penalize_lesson_not_in_ideal_room(constraint_factory),
        #penalize_lesson_in_forbidden_timeslot(constraint_factory)
        #multiple_groups_same_subject_together()
        # Soft constraints are only implemented in the optapy-quickstarts code
    ]

def room_conflict(constraint_factory):
    # A room can accommodate at most one lesson at the same time.
    return constraint_factory \
            .forEach(LessonClass) \
            .join(LessonClass,
                [
                    # ... in the same timeslot ...
                    Joiners.equal(lambda lesson: lesson.timeslot),
                    # ... in the same room ...
                    Joiners.equal(lambda lesson: lesson.room),
                    # ... and the pair is unique (different id, no reverse pairs) ...
                    Joiners.lessThan(lambda lesson: lesson.id)
                ]) \
            .penalize("Room conflict", HardSoftScore.ONE_HARD)

def teacher_conflict(constraint_factory):
    # A teacher can teach at most one lesson at the same time.
    return constraint_factory \
                .forEach(LessonClass)\
                .join(LessonClass,
                        [
                            Joiners.equal(lambda lesson: lesson.timeslot),
                            Joiners.equal(lambda lesson: lesson.teacher.name),
                    Joiners.lessThan(lambda lesson: lesson.id)
                        ]) \
                .penalize("Teacher conflict", HardSoftScore.ONE_HARD)

def student_group_conflict(constraint_factory):
    # A student can attend at most one lesson at the same time.
    return constraint_factory \
            .forEach(LessonClass) \
            .join(LessonClass,
                [
                    Joiners.equal(lambda lesson: lesson.timeslot),
                    Joiners.equal(lambda lesson: lesson.student_group),
                    Joiners.lessThan(lambda lesson: lesson.id)
                ]) \
            .penalize("Student group conflict", HardSoftScore.ONE_HARD)

def multiple_groups_same_subject_together(constraint_factory):
    # If two student groups are listening to the same subject at the same time,
    # they must be in the same room.
    return constraint_factory \
            .forEach(LessonClass) \
            .join(LessonClass,
                [
                    # ... in the same timeslot ...
                    Joiners.equal(lambda lesson: lesson.timeslot),
                    # ... for the same subject ...
                    Joiners.equal(lambda lesson: lesson.subject),
                    # ... and the pair is unique (different id, no reverse pairs) ...
                    Joiners.lessThan(lambda lesson: lesson.id),
                    # ... but different student groups ...
                    Joiners.filtering(lambda lessonA, lessonB: lessonA.student_group != lessonB.student_group),
                    # ... and different rooms ...
                    Joiners.filtering(lambda lessonA, lessonB: lessonA.room != lessonB.room)
                ]) \
            .penalize("Multiple student groups for the same subject must be together", HardSoftScore.ONE_HARD)

def room_capacity_conflict(constraint_factory):
    # A room must have a capacity greater than or equal to the student group size.
    return constraint_factory \
        .forEach(LessonClass) \
        .filter(lambda lesson: lesson.room is not None and
                lesson.room.capacity < lesson.student_group_capacity) \
        .penalize("Room capacity conflict", HardSoftScore.ONE_HARD)

def teacher_availability_conflict(constraint_factory):
    # A lesson can only be scheduled in a time slot if the teacher is available.
    return constraint_factory \
        .forEach(LessonClass) \
        .filter(lambda lesson: not lesson.teacher.is_available(lesson.timeslot)) \
        .penalize("Teacher availability conflict", HardSoftScore.ONE_HARD)

def student_conflict(constraint_factory):
    # Students in intersecting groups cannot attend lessons at the same time.
    return constraint_factory \
        .forEach(LessonClass) \
        .join(LessonClass,
              [
                  Joiners.equal(lambda lesson: lesson.timeslot),
                  Joiners.lessThan(lambda lesson: lesson.id),
                  # Check if the student groups of the two lessons intersect
                  Joiners.filtering(lambda lessonA, lessonB:
                                    group_intersection.get(lessonA.student_group.name, {}).get(lessonB.student_group.name, 0) == 1 or
                                    group_intersection.get(lessonB.student_group.name, {}).get(lessonA.student_group.name, 0) == 1)
              ]) \
        .penalize("Student conflict", HardSoftScore.ONE_HARD)

def penalize_lesson_not_in_ideal_timeslot(constraint_factory):
    # Apply a penalty if a lesson's timeslot is not the same as its ideal timeslot.
    return constraint_factory \
        .forEach(Lesson) \
        .filter(lambda lesson: lesson.ideal_timeslot is not None and lesson.timeslot != lesson.ideal_timeslot) \
        .penalize("Lesson not in ideal timeslot", HardSoftScore.ofHard(100))  # Increased penalty

def penalize_lesson_not_in_ideal_room(constraint_factory):
    # Apply a penalty if a lesson's room is not the same as its ideal room.
    return constraint_factory \
        .forEach(Lesson) \
        .filter(lambda lesson: lesson.ideal_room is not None and lesson.room != lesson.ideal_room) \
        .penalize("Lesson not in ideal room", HardSoftScore.ofHard(120))  # Increased penalty

def penalize_lesson_in_forbidden_timeslot(constraint_factory):
    # Apply a penalty for each lesson that is scheduled in a forbidden timeslot.
    return constraint_factory \
        .forEach(Lesson) \
        .filter(lambda lesson: lesson.timeslot in lesson.forbidden_timeslots) \
        .penalize("Lesson in forbidden timeslot", HardSoftScore.ofHard(150))  # The penalty can be adjusted as needed

solver_config = optapy.config.solver.SolverConfig().withEntityClasses(get_class(Lesson)) \
    .withSolutionClass(get_class(TimeTable)) \
    .withConstraintProviderClass(get_class(define_constraints)) \
    .withTerminationSpentLimit(Duration.ofSeconds(30)) \
    .withPhases([
        optapy.config.constructionheuristic.ConstructionHeuristicPhaseConfig(),
        optapy.config.localsearch.LocalSearchPhaseConfig()
            .withAcceptorConfig(optapy.config.localsearch.decider.acceptor.LocalSearchAcceptorConfig()
                                .withSimulatedAnnealingStartingTemperature("0hard/0soft"))
    ])    

def main():
    st.title("File Upload and Information")

    # Create a file uploader widget
    uploaded_file = st.file_uploader("Choose a file")

    if uploaded_file is not None:
        # Get file size in bytes
        file_size_bytes = len(uploaded_file.getvalue())
        
        # Convert bytes to megabytes (MB)
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Display the file information
        st.write(f"Filename: {uploaded_file.name}")
        st.write(f"Filesize: {file_size_mb:.2f} MB")

        # Process the file
        process_file(uploaded_file)

        create_schedule()

def process_file(uploaded_file):
    # Create a directory to save files
    save_dir = 'uploaded_files'
    os.makedirs(save_dir, exist_ok=True)

    # Read the Excel file (all sheets)
    with pd.ExcelFile(uploaded_file) as xls:
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name)
            
            # Construct the filename for each sheet
            save_path = os.path.join(save_dir, f"{sheet_name}.csv")
            
            # Save each sheet as a CSV file
            df.to_csv(save_path, index=False)
            st.write(f"Saved {sheet_name} to {save_path}")
    
def preprocess_input(input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df):
    global group_intersection
    input_lessons_df = input_lessons_df[input_lessons_df['format'] == 'офлайн']
    # input_lessons_df['subject'] = input_lessons_df['subject'] + ' '  + input_lessons_df['is_lection'].apply(lambda val:'[Лекція]' if  val == 1 else '[Практика]').copy()
    input_lessons_df['count'] = input_lessons_df['count'].astype(int)
    duplicated_rows = pd.DataFrame(input_lessons_df.loc[input_lessons_df.index.repeat(input_lessons_df['count'])].reset_index(drop=True))
    duplicated_rows.drop('count', axis=1, inplace=True)
    input_lessons_df = duplicated_rows.copy()
    input_lessons_df['id'] = np.arange(input_lessons_df.shape[0])

    group_intersection = get_group_intersections(input_students_df)
    input_teachers_df['name'] = input_teachers_df['name'].apply(lambda v: v.rstrip().lstrip())

    group_to_pupils = {}

    for subject in input_students_df.columns[3:]:
        d = input_students_df[subject].value_counts().to_dict()
        d = {k.rstrip().lstrip(): v for k, v in d.items()}
        group_to_pupils.update(d)

    input_lessons_df['pupils'] = input_lessons_df['group'].apply(lambda v: group_to_pupils.get(v, -1))
    input_lessons_df = input_lessons_df[input_lessons_df['pupils'] != - 1]

    group_to_id = {k: num for num, (k,v) in enumerate(group_to_pupils.items())}
    st.write('total group_to_id', len(group_to_id))

    input_audiences_df = input_audiences_df[~pd.isna(input_audiences_df['is_shelter_id'])].copy()
    input_audiences_df.loc[:, 'name'] = input_audiences_df.apply(lambda row: f"{row['id']}_{row['name']}", axis=1)
    input_audiences_df['id'] = np.arange(input_audiences_df.shape[0])

    input_students_df['id'] = np.arange(input_students_df.shape[0])

    for c in input_students_df.columns[3:]:
        input_students_df[c] = input_students_df[c].astype(str).str.strip()

    input_students_df = input_students_df.replace('nan', np.nan)
    input_students_df['name'] = input_students_df['Прізвище'] + ' ' +  input_students_df["Ім'я"]
    input_audiences_df['capacity'] = input_audiences_df.apply(lambda row: row['capacity'] + 50 if row['name'] == '1003_TA Ventures Classroom' else row['capacity'], axis=1)
    input_audiences_df['capacity'] = input_audiences_df['capacity'] + 30
    #input_lessons_df = input_lessons_df.drop_duplicates(['subject', 'group'])
    #input_lessons_df.shape


    timeslot_list = get_timeslot_list()
    timeslot_dict = {day: [] for day in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']}
    for timeslot in timeslot_list:
        timeslot_dict[timeslot.day_of_week].append(timeslot)
        
    input_teachers_df = input_teachers_df.replace('online ', 1).fillna(1)
    teachers_availability = get_teacher_availability(input_teachers_df, timeslot_dict)


    def foo(v):
        r = {}
        for k_1,v_1 in v.items():
            for k_2,v_2 in v_1.items():
                r[k_2] = v_2
        return r

    teachers_availability = {k: foo(v) for k, v in teachers_availability.items()}

    return input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df, teachers_availability, group_to_id, group_intersection, group_to_pupils 

def generate_problem(input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df, teachers_availability, group_to_id, group_intersection, group_to_pupils ):
    timeslot_list = get_timeslot_list()

    room_list = []
    for _, row in input_audiences_df.iterrows():
      room_list.append(Room(row['id'], row['name'], row['capacity']))

    group_objects = {}
    for group_name, pupils in group_to_pupils.items():
        group_id = group_to_id[group_name]
        group_objects[group_name] = StudentGroup(group_id, group_name, pupils)


    lesson_list = []

    for num, (_, row) in enumerate(input_lessons_df.iterrows()):
        try:
            students_df = input_students_df[input_students_df[row['subject'].strip()] ==  row['group']].copy()

            group = group_objects[row['group']] #StudentGroup(group_to_id[row['group']], row['group'], students_df.shape[0])
            lesson = Lesson(num, row['subject'],
                            Teacher(row['teacher'], teachers_availability[row['teacher']]),
                            group, students_df.shape[0])
            #print(lesson)
            lesson_list.append(lesson)
        except Exception as e:
            print('exception', e)

    st.write('lesson_list', len(lesson_list))
    st.write('group_objects', len(group_objects))

    lesson = lesson_list[0]
    lesson.is_pinned = True
    lesson.set_timeslot(timeslot_list[0])
    lesson.set_room(room_list[0])
    
    lesson_list[0] = lesson

    return TimeTable(timeslot_list, room_list, lesson_list)

def get_schedule(input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df, teachers_availability, group_to_id, group_intersection, group_to_pupils ):
    solver_factory = solver_factory_create(solver_config)
    solver = solver_factory.buildSolver()
    solution = solver.solve(generate_problem(input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df, teachers_availability, group_to_id, group_intersection, group_to_pupils ))
    score_manager = score_manager_create(solver_factory)
    explanation = score_manager.explainScore(solution)

    scheduling_records_data = []

    for l in solution.get_lesson_list():
        scheduling_records_data.append({
            'room': f"{l.room.name} [{l.room.capacity}]" ,
            'student_group': f"{l.student_group.name}", # [{l.student_group_capacity}]",
            'subject': l.subject,
            'teacher': ' '.join(l.teacher.name.split(' ')[:2]),
            'day': l.timeslot.day_of_week,
            'start_time': l.timeslot.start_time,
            'lesson_id': l.id,
            'room_id': l.room.id,
            'time_slot_id': l.timeslot.id
        })



    schedule_resuts_df = pd.DataFrame(scheduling_records_data)
    schedule_resuts_df['text'] = schedule_resuts_df.apply(lambda row: f"{row['subject']}\n{row['student_group']}\n{row['teacher']}", axis=1)
    return solution, explanation, schedule_resuts_df


def convert_df_to_csv(df):
    # Convert DataFrame to CSV
    output = StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def create_schedule():
    input_audiences_df = pd.read_csv('uploaded_files/audiences.csv').map(strip_whitespace)
    input_groups_df = pd.read_csv('uploaded_files/groups.csv').map(strip_whitespace)
    input_students_df = pd.read_csv('uploaded_files/students.csv').map(strip_whitespace)
    input_lessons_df = pd.read_csv('uploaded_files/lessons.csv').map(strip_whitespace)

    input_teachers_df = pd.read_csv('uploaded_files/teachers.csv')
    
    input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df, teachers_availability, group_to_id, group_intersection, group_to_pupils  = preprocess_input(input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df)
    st.write('input_audiences_df', input_audiences_df.shape)

    solution, explanation, schedule_resuts_df = get_schedule(input_audiences_df, input_groups_df, input_students_df, input_lessons_df, input_teachers_df, teachers_availability, group_to_id, group_intersection, group_to_pupils)
    unique_rooms = schedule_resuts_df['room'].unique()

    # Convert start_time to a string format for MultiIndex compatibility
    # schedule_resuts_df['start_time'] = schedule_resuts_df['start_time'].apply(lambda t: t.strftime('%H:%M'))

    # Create a pivot table with 'day' and 'start_time' as index, rooms as columns, using 'text' for values
    pivot_df = schedule_resuts_df.pivot_table(index=['day', 'start_time'], 
                                            columns='room', 
                                            values='text', 
                                            aggfunc=lambda x: ' | '.join(x) if len(x) > 0 else '')

    # Reset the column names to just room names for simplicity
    pivot_df.columns = unique_rooms

    # Prepare DataFrame for the grid
    df = pivot_df.copy()
    df = df.fillna('')

    st.write('solution', str(solution.get_score()))
    st.write("Here is the schedule file:")
    st.write(df)

    csv = convert_df_to_csv(df)

    # Create a link to download the CSV file
    st.download_button(
        label="Download schedule file CSV",
        data=csv,
        file_name='dataframe.csv',
        mime='text/csv',
    )


if __name__ == "__main__":
    main()
