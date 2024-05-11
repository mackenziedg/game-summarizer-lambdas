from configparser import ConfigParser
from datetime import date, timedelta
import json
from os import environ, listdir
import sqlite3
from time import monotonic, sleep

import boto3
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


def get_inputs() -> list[dict[str, str]]:
    def dict_factory(cursor, row):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}

    with sqlite3.Connection("/prod.db") as conn:
        conn.row_factory = dict_factory
        res = conn.execute(
            "SELECT * FROM t_game_info ORDER BY date DESC LIMIT 1;"
        )
        most_recent = res.fetchone()["date"]
        res = conn.execute(
            f"SELECT * FROM t_game_info WHERE date = '{most_recent}' ORDER BY date DESC;"
        )
        return res.fetchall()


def format_datatables(data: dict[str, str]) -> str:
    if data["game_number"] == 1:
        multiheader_text = ""
    elif data["game_number"] == 2:
        multiheader_text = "This is game 2 of a doubleheader."
    elif data["game_number"] == 3:
        multiheader_text = "This is game 3 of a tripleheader."
    else:
        print("Four+ games in a day!?!?!")

    return f"""{multiheader_text}
Home Team: {data['home_team_city'] + ' ' + data['home_team_name']}
    Standing: {data['home_standings']}
Away Team: {data['away_team_city'] + ' ' + data['away_team_name']}
    Standing: {data['away_standings']}

==Box Score==
{data['boxscore']}

==Away team batting==
{data['away_batting']}

==Home team batting==
{data['home_batting']}

==Away team pitching==
{data['away_pitching']}

==Home team pitching==
{data['home_pitching']}

==Big plays==
{data['big_plays']}
"""


def save_summary(summary: dict[str, str]):
    with sqlite3.Connection("/prod.db") as conn:
        conn.execute(
            f"INSERT INTO t_llm_output_data VALUES (?, ?);",
            (summary["game_id"], summary["summary"]),
        )
        conn.commit()


def get_prompt() -> str:
    prompt_path = sorted(listdir("prompts/"))[-1]  # Get most recent prompt
    with open(f"prompts/{prompt_path}") as f:
        return f.read()


def build_chain():
    model = ChatAnthropic(model="claude-3-haiku-20240307")
    prompt = ChatPromptTemplate.from_template(get_prompt())
    output_parser = StrOutputParser()
    return prompt | model | output_parser


def main() -> str:
    fn_start = monotonic()

    llm_inputs = get_inputs()
    chain = build_chain()

    for ix, llm_input in enumerate(llm_inputs):
        print(f"{ix+1}/{len(llm_inputs)}")
        formatted = format_datatables(llm_input)
        save_summary(
            {
                "game_id": llm_input["game_id"],
                "summary": chain.invoke({"data": formatted}),
            }
        )
        sleep(12)

    print(f"Finished generate-summaries in {monotonic() - fn_start} s.")


if __name__ == "__main__":
    with open("/run/secrets/ANTHROPIC_API_KEY") as f:
        environ["ANTHROPIC_API_KEY"] = f.read().strip()
    main()
