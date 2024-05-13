import json
from os import environ, listdir
from time import monotonic, sleep

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

# Volume defined in compose.yaml
LLM_INPUT_DIRECTORY: str = "/llm_data/llm_inputs"
LLM_OUTPUT_DIRECTORY: str = "/llm_data/llm_outputs"


def get_inputs() -> list[dict[str, str]]:
    def read_file(path: str) -> dict[str, str]:
        with open(f"{LLM_INPUT_DIRECTORY}/{path}") as f:
            return json.load(f)

    def get_file_date(filename: str) -> str:
        return filename.split("_")[0]

    most_recent_date = get_file_date(max(listdir(LLM_INPUT_DIRECTORY)))
    return [
        read_file(f)
        for f in [
            p
            for p in listdir(LLM_INPUT_DIRECTORY)
            if get_file_date(p) == most_recent_date
        ]
    ]


def format_datatables(data: dict[str, str]) -> str:
    if data["game_number"] == 1:
        multiheader_text = ""
    elif data["game_number"] == 2:
        multiheader_text = "This is game 2 of a doubleheader."
    elif data["game_number"] == 3:
        multiheader_text = "This is game 3 of a tripleheader."
    else:
        multiheader_text = ""
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


def save_summary(data_dict: dict[str, str]):
    # TODO: Don't like that this is duplicated from pull_boxscores:save_data
    filename: str = (
        f"{data_dict['date']}_{data_dict['home_team_name']}\
        _at_{data_dict['away_team_name']}_{data_dict['game_number']}"
    )

    with open(f"{LLM_OUTPUT_DIRECTORY}/{filename}.json", "w") as f:
        json.dump(data_dict, f)


def get_prompt(prompt_type: str) -> str:
    prompt_path = sorted(listdir(f"/llm_data/prompts/{prompt_type}/"))[
        -1
    ]  # Get most recent prompt
    with open(f"/llm_data/prompts/{prompt_type}/{prompt_path}") as f:
        return f.read()


def build_chain(prompt_type: str):
    prompt = ChatPromptTemplate.from_template(get_prompt(prompt_type))
    output_parser = StrOutputParser()

    if prompt_type == "summarize":
        model = ChatAnthropic(model="claude-3-haiku-20240307")
    elif prompt_type == "translate":
        model = ChatAnthropic(model="claude-3-sonnet-20240229")
    else:
        raise ValueError(f"Invalid prompt type: {prompt_type}")

    return prompt | model | output_parser


def main(test: int | None = None):
    fn_start = monotonic()

    data_dicts = get_inputs()[:test]
    summary_chain = build_chain("summarize")
    translate_chain = build_chain("translate")

    for ix, d in enumerate(data_dicts):
        print(f"{ix + 1}/{len(data_dicts)}")
        formatted = format_datatables(d)
        d["summary_en"] = summary_chain.invoke({"data": formatted})
        sleep(1)  # Just being safe with rate limits
        d["summary_es"] = translate_chain.invoke({"article": d["summary_en"]})
        sleep(1)  # Just being safe with rate limits
        save_summary(d)

    print(f"Finished generate-summaries in {monotonic() - fn_start:.1f} s.")


if __name__ == "__main__":
    with open("/run/secrets/ANTHROPIC_API_KEY") as f:
        environ["ANTHROPIC_API_KEY"] = f.read().strip()
    print("Detected test flag. Limiting number of pulls.")
    if environ["GS_TEST"] == "1":
        main(2)
    else:
        main()
