import json
from rits.rits_runner import RITS
import os
import warnings
import logging
from config_full import get_settings
from dotenv import load_dotenv
load_dotenv()
import ast
from schema_linking import schema_store
from sql_components.executor import ExecutorCreds, SQLQueryExecutor

warnings.filterwarnings("ignore")
logging.basicConfig(filename='./logger/qgen_logger_diagnostic.log', level=logging.INFO, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

host = get_settings().mysql_host
user = get_settings().mysql_user
pswd = os.getenv('MYSQL_PASSWORD')
port = get_settings().mysql_port

exec_creds = ExecutorCreds(
    host=host,
    user=user,
    password=pswd,
    port=port
)

def run_query(exec_creds, query):
  return SQLQueryExecutor(exec_creds).run(query)
# export PYTHONPATH="${PYTHONPATH}:/home/shivangi/data-to-story"

class benchmarking():
    def __init__(self, schema_path, apikey=os.getenv('RITS_APIKEY'), url=get_settings().rits_llama_url, model_id=get_settings().model_llama):
        self.schema_path = schema_path
        self.repetition_penalty = 1.02
        self.max_new_tokens = 1500
        self.min_new_tokens = 1
        self.temperature = 0.05
        self.q_count_threshld = 9
        model_id = "meta-llama/llama-3-3-70b-instruct"
        url = "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/llama-3-3-70b-instruct/v1/completions"
        self.rits = RITS(uri=url, api_key=apikey, model_name=model_id)

    def get_diagnostic_prompt(self, schema):
        return """## Task:

You are an expert in Business Intelligence (BI) and Data Analytics. Your objective is to generate **diagnostic analytical questions** that help uncover **underlying reasons, contributing factors, and relationships behind observed patterns or outcomes** in a business dataset.

## What Are Diagnostic Analytical Questions?

Diagnostic questions focus on understanding **why something happened**, by exploring **drivers, influencing factors, relationships, root causes, correlations, and segment-wise variations** in historical data.

Diagnostic questions aim to go **beyond just what happened**, to explain **what caused it, what influenced it, or how different dimensions contribute to it**.

## How Should These Questions Be Framed?

1. **Use business-friendly language** — business users do not refer to table or column names in queries.
2. **Avoid explicit mentions of table/column names** in the question text.
3. **Ensure each question reflects natural business thinking**.
4. **Questions should be self-contained and clear**, so they can be answered directly using the dataset.

## Complexity Levels

1. **Basic** – High-level questions on causes, drivers, or dimension-wise contribution
   *Example: “What factors contributed to the decline in customer orders?”*

2. **Intermediate** – Segment-wise diagnosis or breakdowns of key changes or outcomes
   *Example: “How did different regions contribute to the drop in quarterly revenue?”*

3. **Advanced** – Multi-factor analysis, correlation-based reasoning, or comparative root cause exploration
   *Example: “What are the key customer attributes driving churn in high-value segments?”*

## Instructions:

1. Generate exactly **9 diagnostic questions** in total : **3 Basic**, **3 Intermediate**, and **3 Advanced**.
2. Each question should be **fully answerable using the given dataset schema**.
3. Avoid questions that require external data or are ambiguous.
4. Use specific **business contexts** like customer behavior, product sales, regional trends, time-based diagnosis, etc.
5. **Avoid mentioning actual table or column names in the question text.**
6. **Enclose each question within `<question>...</question>` tags.**
7. Return a clean, structured output in JSON format with each question and its complexity level.
8. **Again, do not return anything except the raw JSON array. Avoid any headings, notes, or boxed formats.**
9. All 9 questions must be returned in a **single flat JSON array**.
10. Do **not create multiple arrays or group questions by complexity** — just one array with 9 JSON objects.

Ensure:

1. Each question must be fully answerable using only the columns and data types explicitly provided in the schema.
2. Do not invent additional columns or assume missing information.
3. Only use the column names and sample values shown in the schema.
4. If a question depends on unavailable data, skip it.
5. Do not make assumptions about data availability or granularity (e.g., specific time periods, locations, customer types, etc.) unless clearly stated in the schema.
- Prefer: “...across segments”, “by region”, “based on customer type”
- Avoid: “last year”, “premium customers”, “city-wise” if such details are not explicitly part of the dataset.

## Dataset Schema:

""" + schema + """

## Output Format:

```json
[
  {
    "question": "<question_text>",
    "complexity": "Basic | Intermediate | Advanced"
  }
]

Return a single JSON array named `questions`, not multiple arrays."""


    def postprocess_response(self, response):
        # Find all question entries
        json_str = response.split("json")[1].split("]")[0] +"]"
        print("#########################################");
        ques_complexity_list = ast.literal_eval(json_str)
        return ques_complexity_list
    
    def generate(self, database_name):
        ques_complexity_list, response = [], ""
        try:
            table_names_query = "SHOW TABLES IN " + database_name + ";"
            input_tuples = run_query(exec_creds, table_names_query)
            database_tables = [item[0] for item in input_tuples]

            schema = schema_store.read_schema(self.schema_path, database_name, database_tables)

            prompt = self.get_diagnostic_prompt(schema)
            response = self.rits.post(input=prompt, temperature=self.temperature, max_new_tokens=self.max_new_tokens, repetition_penalty=self.repetition_penalty)
            logger.info("Questions generated:\n" + response)
            if response:
                ques_complexity_list = self.postprocess_response(response)
        except Exception as e:
            print(e);
            logger.error(e)
            return None
        finally:
            return ques_complexity_list

if __name__ == "__main__":
    schema_path = "./question_generation_benchmarking/database_schemas.json"
    benchmark = benchmarking(schema_path)
    input_tuples = run_query(exec_creds, "SHOW DATABASES;")
    database_names = [item[0] for item in input_tuples]
    database_names.remove("information_schema")
    database_names.remove("mysql")
    database_names.remove("performance_schema")
    database_names.remove("sys")

    ques = {}

    for i in database_names:
        print(i)
        ques[i] = benchmark.generate(i)
    
    file_path = "./question_generation_benchmarking/question_jsons/diagnostic_questions.json"
    with open(file_path, "w") as file:
        json.dump(ques, file)

    print(ques)
