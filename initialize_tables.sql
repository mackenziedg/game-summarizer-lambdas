CREATE TABLE t_game_info (
    game_id INT PRIMARY KEY,
    date TEXT,
    away_team_city TEXT,
    home_team_city TEXT,
    away_team_name TEXT,
    home_team_name TEXT,
    away_standings TEXT,
    home_standings TEXT,
    boxscore TEXT,
    away_batting TEXT,
    home_batting TEXT,
    away_pitching TEXT,
    home_pitching TEXT,
    big_plays TEXT,
    game_number INT
);

CREATE TABLE t_llm_output_data (
    game_id INT PRIMARY KEY,
    summary TEXT,
    FOREIGN KEY(game_id) REFERENCES t_game_info(game_id)
);
