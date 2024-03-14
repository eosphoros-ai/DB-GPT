export LD_LIBRARY_PATH=/datas/liab/DB-GPT/instantclient_21_11
/datas/liab/miniconda3/envs/dbgpt_test/bin/python3 /datas/liab/DB-GPT/db/hr_fk_chinese/CreatePersonnelBasicInfoTableSqlChineseReal.py
echo "[info] a_sap_employee_information_chinese set up success!"
/datas/liab/miniconda3/envs/dbgpt_test/bin/python3 /datas/liab/DB-GPT/db/hr_fk_chinese/CreateaZthrZpListTableSqlChineseReal.py
echo "[info] a_sap_staffing_recruitment_plan_chinese set up success!"
/datas/liab/miniconda3/envs/dbgpt_test/bin/python3 /datas/liab/DB-GPT/db/hr_fk_chinese/CreateEducationInfoTableSqlChineseReal.py
echo "[info] a_sap_employee_education_experience_chinese set up success!"
/datas/liab/miniconda3/envs/dbgpt_test/bin/python3 /datas/liab/DB-GPT/db/hr_fk_chinese/CreatePositionInformationSynchronizationTableSqlChineseReal.py
echo "[info] a_sap_positions_responsibilities_risks_chinese set up success!"
/datas/liab/miniconda3/envs/dbgpt_test/bin/python3 /datas/liab/DB-GPT/db/hr_fk_chinese/CreateReportingRelationshipTableSqlChineseReal.py
echo "[info] a_sap_reporting_relationship_chinese set up success!"
#/datas/liab/miniconda3/envs/dbgpt_test/bin/python3 /datas/liab/DB-GPT/db/hr_fk_chinese/CreatePersonnelAttendanceDetailsSqlChinese.py
#echo "[info] a_sap_employee_attendance_details_chinese set up success!"