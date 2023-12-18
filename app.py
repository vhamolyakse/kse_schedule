import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
from optapy import problem_fact, planning_id
from optapy import solver_factory_create, score_manager_create

from utils.preprocessing import strip_whitespace, get_group_intersections
from utils.entities import StudentGroup, Teacher, Room, Timeslot, Lesson, TimeTable
from utils.time_utils import get_teacher_availability, get_timeslot_list
from utils.constraints import define_constraints, get_solver_config, SOLVING_DURATION
from utils.files import process_file, convert_df_to_csv
from utils.data import DataManager
from utils.schedule import ScheduleManager
from collections import defaultdict
from datetime import time
from optapy import solver_factory_create, score_manager_create
from loguru import logger

from optapy import get_class
import optapy.config
from optapy.types import Duration
from itertools import chain

import streamlit as st
from io import StringIO
import io
import zipfile

from optapy import constraint_provider, get_class
from optapy.constraint import Joiners
from optapy.score import HardSoftScore

RESULT_DATA_PATH = 'new_schedule/input'


def generate_new_schedule(selected_date):
    data_manager = DataManager(RESULT_DATA_PATH)
    problem = data_manager.generate_optapy_problem()
    solver_config = get_solver_config()
    solver_factory = solver_factory_create(solver_config)
    solver = solver_factory.buildSolver()
    st.write(f"Going to create schedule, it will take  {SOLVING_DURATION} seconds")

    solution = solver.solve(problem)
    score_manager = score_manager_create(solver_factory)
    explanation = score_manager.explainScore(solution)

    st.write(f"Final score: {str(solution.get_score())}")
    st.write(f"Score explanation: {str(explanation)}")

    schedule_manager = ScheduleManager(optapy_solution=solution, start_date=selected_date)
    raw_schedule_df = schedule_manager.raw_schedule_df
    json_df = schedule_manager.create_json_from_df(raw_schedule_df)
    pretty_schedule_df = schedule_manager.raw_schedule_to_pretty(raw_schedule_df)
    raw_schedule_csv = convert_df_to_csv(raw_schedule_df)
    pretty_schedule_csv = convert_df_to_csv(pretty_schedule_df)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr('raw_schedule.csv', raw_schedule_csv)
        zip_file.writestr('pretty_schedule.csv', pretty_schedule_csv)
        zip_file.writestr('schedule_data.json', json_df)

    zip_buffer.seek(0)

    st.download_button(
        label="Download Schedules as ZIP",
        data=zip_buffer,
        file_name='schedules.zip',
        mime='application/zip'
    )


if 'alternatives_for_selected_lesson' not in st.session_state:
    st.session_state['alternatives_for_selected_lesson'] = []
if 'alternatives_new_raw_schedule_df' not in st.session_state:
    st.session_state['alternatives_new_raw_schedule_df'] = []


def main():
    st.title('Schedule optimisation')

    selected_date = st.date_input("Select the date for Monday")

    if selected_date.weekday() != 0:
        st.error("Please select a Monday.")
        return

    uploaded_file = st.file_uploader("Input data for schedule")
    if uploaded_file is not None:
        process_file(uploaded_file, RESULT_DATA_PATH)

    if st.button('Generate new schedule'):
        generate_new_schedule(selected_date)

    existing_schedule_file = st.file_uploader("Existing raw schedule")
    print(existing_schedule_file)

    if existing_schedule_file is not None:
        logger.debug('Existing schedule')
        raw_schedule_df = pd.read_csv(existing_schedule_file)

        schedule_manager = ScheduleManager(raw_schedule_df=raw_schedule_df, start_date=selected_date)
        import pdb

        selected_option = st.selectbox('Choose the lection you would like to resckedule:',
                                       raw_schedule_df['text'].values.tolist())

        if st.button('Show me alternative time splots'):

            lesson_id = int(re.search(r'\[([0-9]+)\]', selected_option).group(1))

            logger.debug(f'Selected lesson_id {lesson_id}')
            seleted_lesson_row = raw_schedule_df[raw_schedule_df['lesson_id'] == lesson_id].iloc[0]
            forbidden_time_slots = {seleted_lesson_row['time_slot_id']: 1}
            logger.debug(f'Initial forbidden time slots: {forbidden_time_slots}')
            data_manager = DataManager(RESULT_DATA_PATH, existing_schedule_df=raw_schedule_df)

            for i in range(2):
                logger.debug(f'For i : {i} forbidden time slots: {forbidden_time_slots}')
                problem = data_manager.generate_optapy_problem(reschedule_lesson_id=lesson_id,
                                                               forbidden_time_slots=forbidden_time_slots)
                solver_config = get_solver_config()
                solver_factory = solver_factory_create(solver_config)
                solver = solver_factory.buildSolver()
                st.write(f"Going to create schedule, it will take  {SOLVING_DURATION} seconds")

                solution = solver.solve(problem)
                # st.write(f"Final score: {str(solution.get_score())}")
                if str(solution.get_score()) != '0hard/0soft':
                    logger.debug('Solution is not good')
                    continue
                else:
                    st.write(f"We have one more alternative slot")

                new_raw_schedule_df = ScheduleManager(optapy_solution=solution, start_date=selected_date).raw_schedule_df
                new_lesson_raw_schedule = new_raw_schedule_df[new_raw_schedule_df['lesson_id'] == lesson_id].iloc[0]
                forbidden_time_slots.update({new_lesson_raw_schedule['time_slot_id']: 1})
                logger.debug(f'Forbidden time slots: {forbidden_time_slots}')
                logger.debug(f"New time slot: {new_lesson_raw_schedule['time_slot_id']}")

                st.session_state['alternatives_for_selected_lesson'].append(
                    f"{new_lesson_raw_schedule['day']} {new_lesson_raw_schedule['start_time']} {new_lesson_raw_schedule['room']}"
                )
                st.session_state['alternatives_new_raw_schedule_df'].append(new_raw_schedule_df)
                logger.debug(st.session_state['alternatives_for_selected_lesson'])

    print('UPDATED VERSIONS')
    if st.session_state['alternatives_for_selected_lesson']:
        selected_option = st.selectbox('Please choose alternative time slot:',
                                       st.session_state['alternatives_for_selected_lesson'])

        if st.button('Update schedule'):
            selected_index = st.session_state['alternatives_for_selected_lesson'].index(selected_option)
            new_raw_schedule_df = st.session_state['alternatives_new_raw_schedule_df'][selected_index]

            import pdb
            pdb.set_trace()

            new_pretty_schedule_df = schedule_manager.raw_schedule_to_pretty(new_raw_schedule_df)
            raw_schedule_csv = convert_df_to_csv(new_raw_schedule_df)
            pretty_schedule_csv = convert_df_to_csv(new_pretty_schedule_df)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                zip_file.writestr('raw_schedule.csv', raw_schedule_csv)
                zip_file.writestr('pretty_schedule.csv', pretty_schedule_csv)

            zip_buffer.seek(0)

            # Create a link to download the zip file
            st.download_button(
                label="Download updated schedules as ZIP",
                data=zip_buffer,
                file_name='schedules.zip',
                mime='application/zip'
            )


if __name__ == "__main__":
    main()
