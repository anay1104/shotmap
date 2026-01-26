import matplotlib.pyplot as plt  # type: ignore
import matplotlib.font_manager as fm  # type: ignore
from mplsoccer import VerticalPitch  # type: ignore
import json
import pandas as pd
import time
import requests
from io import BytesIO
import streamlit as st  # type: ignore

st.set_page_config(page_title="Shotmap Generator", page_icon=":soccer:")


@st.cache_data
def load_data():
    with open("players/players_data.json", encoding="utf-8") as p:
        loaded = json.load(p)
    df = pd.DataFrame(loaded)
    return df


@st.cache_data
def get_player_understat_data(player_id):
    base_url = "https://understat.com"
    player_url = f"{base_url}/getPlayerData/{player_id}"

    try:
        with requests.Session() as session:
            session.headers.update(
                {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
            )
            r = session.get(player_url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        return None
    return None


@st.cache_data
def check_if_team_in_league(league_name, season, team_name):
    url = f"https://understat.com/getLeagueData/{league_name}/{season}"
    try:
        with requests.Session() as session:
            session.headers.update(
                {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
            )
            r = session.get(url)
            if r.status_code == 200:
                data = r.json()
                main_data = data.get("dates", data.get("date", []))
                for match in main_data:
                    home_team = match.get("h", {}).get("title")
                    away_team = match.get("a", {}).get("title")
                    if home_team == team_name or away_team == team_name:
                        return True
    except Exception:
        return False
    return False


players_data = load_data()
player_names = sorted(players_data["name"].unique().tolist())


if "visitor_count" not in st.session_state:
    st.session_state.visitor_count = 0

st.session_state.visitor_count += 1

if "generate_plot" not in st.session_state:
    st.session_state.generate_plot = False
if "results_cache" not in st.session_state:
    st.session_state.results_cache = {}

st.title("Shot Map Generator")
st.markdown(
    "Created by Anay Shukla | Twitter: [@BetterThanMario](https://twitter.com/BetterThanMario) | Bluesky: [@luigi1104.bsky.social](https://bsky.app/profile/luigi1104.bsky.social)"
)

st.header("About")
st.write(
    "Generates a shot map visualization of a player currently playing in the top 5 European leagues (PL, La Liga, Serie A, Bundesliga, Ligue 1) and RFPL. Data sourced from [Understat](https://understat.com)."
)

tab1, tab2, tab3 = st.tabs(["Main", "Output", "FAQ"])

with tab1:
    with st.container(height=190, border=True, width=2500):
        input1 = st.selectbox(
            "Select player",
            options=player_names,
            index=None,
            placeholder="Type to search or select a player...",
        )

        player_json_data = None
        player_id = None
        available_seasons = []

        if input1:
            # 1. Find Player ID
            closest = input1
            new_df = players_data[players_data["name"] == closest]

            if new_df.empty:
                st.error(f"Error: Could not find data for {input1}.")
                st.stop()

            if "id" in new_df.columns:
                player_id = str(new_df.iloc[0]["id"])
            else:
                player_id = str(new_df.iloc[0, 0])

            player_json_data = get_player_understat_data(player_id)

            if (
                player_json_data
                and "groups" in player_json_data
                and "season" in player_json_data["groups"]
            ):
                season_list = player_json_data["groups"]["season"]
                unique_seasons = set(item["season"] for item in season_list)
                available_seasons = sorted(list(unique_seasons), reverse=True)

        season = st.selectbox(
            "Select season",
            options=available_seasons,
            placeholder="Select a season... (Each season corresponds to the starting year, e.g., 2023 for 2023/24)",
            disabled=not available_seasons,
        )

    button = st.button("Generate Shot Map")

    if "fig" not in st.session_state:
        st.session_state.fig = None

    if button and input1 and season:
        cache_key = f"{input1.lower()}_{season}"
        if cache_key in st.session_state.results_cache:
            st.session_state.fig = st.session_state.results_cache[cache_key]
            st.session_state.generate_plot = True
            st.info("Retrieved from cache. Click on the Output tab to see the plot.")
        else:
            current_time = time.time()

            st.session_state.last_request_time = current_time

            if not season.isdigit() or len(season) != 4:
                st.error("Please enter a valid year.", icon=":material/error:")
            else:
                with st.spinner(
                    "Generating shot map, should take less than 10 seconds (feel free to browse through the FAQ section!)...",
                    show_time=True,
                ):
                    try:
                        if not player_json_data:
                            st.error("Could not retrieve data from Understat.")
                            st.stop()

                        shots_data = player_json_data["shots"]
                        df = pd.DataFrame(shots_data)
                        df = df[df["season"] == season]

                        if df.empty:
                            st.error(f"No shots found for {input1} in {season}")
                            st.stop()

                        df["X"] = pd.to_numeric(df["X"])
                        df["Y"] = pd.to_numeric(df["Y"])
                        df["xG"] = pd.to_numeric(df["xG"])

                        player_name = input1

                        season_groups = player_json_data.get("groups", {}).get(
                            "season", []
                        )

                        current_season_entries = [
                            item
                            for item in season_groups
                            if str(item["season"]) == str(season)
                        ]

                        unique_teams = list(
                            set(item["team"] for item in current_season_entries)
                        )

                        leagues_to_check = [
                            "EPL",
                            "La_liga",
                            "Bundesliga",
                            "Serie_A",
                            "Ligue_1",
                            "RFPL",
                        ]
                        final_team_strings = []

                        progress_text = st.empty()
                        progress_text.text("Verifying leagues...")

                        for team in unique_teams:
                            found_league = None
                            for league in leagues_to_check:
                                if check_if_team_in_league(league, season, team):
                                    found_league = league
                                    break

                            if found_league:
                                clean_league = found_league.replace("_", " ")
                                final_team_strings.append(f"{team} ({clean_league})")
                            else:
                                final_team_strings.append(f"{team} (Unknown)")

                        progress_text.empty()
                        teams_title_str = " + ".join(final_team_strings)

                        current_stats = [
                            item
                            for item in season_groups
                            if str(item["season"]) == str(season)
                        ]

                        if current_stats:
                            total_time = sum(
                                float(item["time"]) for item in current_stats
                            )
                            total_xg_season = sum(
                                float(item["xG"]) for item in current_stats
                            )
                            total_xa_season = sum(
                                float(item["xA"]) for item in current_stats
                            )
                            total_shots_season = sum(
                                int(item["shots"]) for item in current_stats
                            )
                            total_npxg_season = sum(
                                float(item["npxG"]) for item in current_stats
                            )
                        else:
                            total_time = 0
                            total_xg_season = 0
                            total_xa_season = 0
                            total_shots_season = 0
                            total_npxg_season = 0

                        if total_time > 0:
                            xg_p90 = total_xg_season / (total_time / 90)
                            shots_p90 = total_shots_season / (total_time / 90)
                            npxg_p90 = total_npxg_season / (total_time / 90)
                            xgi_p90 = (total_xg_season + total_xa_season) / (
                                total_time / 90
                            )

                        df["X"] = pd.to_numeric(df["X"])
                        df["Y"] = pd.to_numeric(df["Y"])
                        df["xG"] = pd.to_numeric(df["xG"])

                        df["X"] = df["X"] * 100
                        df["Y"] = df["Y"] * 100

                        number_of_shots = df.shape[0]
                        number_of_goals = df[df["result"] == "Goal"].shape[0]
                        number_of_xg = df["xG"].sum()
                        xg_per_shot = number_of_xg / float(number_of_shots)

                        background_color = "#484e48"
                        background_color2 = "#2c932f"

                        font_path = "lato/Lato-Regular.ttf"
                        font_props = fm.FontProperties(fname=font_path)

                        fig = plt.figure(figsize=(9, 13))
                        fig.patch.set_facecolor(background_color)

                        ax1 = fig.add_axes([0, 0.7, 1, 0.2])
                        for spine in ax1.spines.values():
                            spine.set_visible(False)
                        ax1.set_xticks([])
                        ax1.set_yticks([])
                        ax1.set_facecolor(background_color)
                        ax1.set_xlim(0, 1)
                        ax1.set_ylim(0, 1)

                        ax1.text(
                            x=0.5,
                            y=0.85,
                            s=player_name,
                            fontsize=25,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="center",
                        )

                        season_short = season[2:4]
                        next_season_short = int(season_short) + 1

                        ax1.text(
                            x=0.5,
                            y=0.71,
                            s=f"Shot Map at {teams_title_str} for the {season_short}/{next_season_short} Season",
                            fontsize=13,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="center",
                        )

                        ax1.text(
                            x=0.27,
                            y=0.5,
                            s="Low Quality Chance",
                            fontsize=12,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="center",
                        )

                        ax1.scatter(
                            x=0.37,
                            y=0.53,
                            s=100,
                            color=background_color,
                            edgecolor="white",
                            linewidth=0.8,
                        )

                        ax1.scatter(
                            x=0.42,
                            y=0.53,
                            s=200,
                            color=background_color,
                            edgecolor="white",
                            linewidth=0.8,
                        )

                        ax1.scatter(
                            x=0.48,
                            y=0.53,
                            s=300,
                            color=background_color,
                            edgecolor="white",
                            linewidth=0.8,
                        )

                        ax1.scatter(
                            x=0.54,
                            y=0.53,
                            s=400,
                            color=background_color,
                            edgecolor="white",
                            linewidth=0.8,
                        )

                        ax1.scatter(
                            x=0.61,
                            y=0.53,
                            s=500,
                            color=background_color,
                            edgecolor="white",
                            linewidth=0.8,
                        )

                        ax1.text(
                            x=0.723,
                            y=0.5,
                            s="High Quality Chance",
                            fontsize=12,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="center",
                        )

                        ax1.text(
                            x=0.096,
                            y=0.286,
                            s="- Shot Saved",
                            fontsize=10,
                            fontproperties=font_props,
                            color="white",
                        )

                        ax1.scatter(
                            x=0.08,
                            y=0.3,
                            s=150,
                            color="yellow",
                            edgecolor="white",
                            linewidth=0.8,
                            alpha=0.7,
                        )

                        ax1.text(
                            x=0.216,
                            y=0.286,
                            s="- Blocked/Off Target",
                            fontsize=10,
                            fontproperties=font_props,
                            color="white",
                        )

                        ax1.scatter(
                            x=0.2,
                            y=0.3,
                            s=150,
                            color=background_color,
                            edgecolor="white",
                            linewidth=0.8,
                            alpha=0.7,
                        )

                        ax1.text(
                            x=0.396,
                            y=0.286,
                            s="- Goal",
                            fontsize=11,
                            fontproperties=font_props,
                            color="white",
                        )

                        ax1.scatter(
                            x=0.38,
                            y=0.3,
                            s=150,
                            color="red",
                            edgecolor="white",
                            linewidth=0.8,
                            alpha=0.7,
                        )

                        ax1.text(
                            x=0.486,
                            y=0.286,
                            s="- Penalty Scored",
                            fontsize=11,
                            fontproperties=font_props,
                            color="white",
                        )

                        ax1.scatter(
                            x=0.47,
                            y=0.3,
                            s=150,
                            color="blue",
                            marker="s",
                            edgecolor="white",
                            linewidth=0.8,
                            alpha=0.7,
                        )

                        ax1.text(
                            x=0.646,
                            y=0.286,
                            s="- Penalty Missed",
                            fontsize=11,
                            fontproperties=font_props,
                            color="white",
                        )

                        ax1.scatter(
                            x=0.63,
                            y=0.3,
                            s=150,
                            color="violet",
                            marker="s",
                            edgecolor="white",
                            linewidth=0.8,
                            alpha=0.7,
                        )

                        ax1.text(
                            x=0.806,
                            y=0.286,
                            s="- Freekick Scored",
                            fontsize=11,
                            fontproperties=font_props,
                            color="white",
                        )

                        ax1.scatter(
                            x=0.79,
                            y=0.3,
                            s=150,
                            color="turquoise",
                            marker="^",
                            edgecolor="white",
                            linewidth=0.8,
                            alpha=0.7,
                        )

                        ax1.text(
                            x=0.83,
                            y=-0.1,
                            s="xG per 90",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax1.text(
                            x=0.88,
                            y=-0.23,
                            s=f"{xg_p90:.2f}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax1.text(
                            x=0.82,
                            y=-0.51,
                            s="Shots per 90",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax1.text(
                            x=0.88,
                            y=-0.63,
                            s=f"{shots_p90:.2f}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax1.text(
                            x=0.82,
                            y=-0.9,
                            s="npxG per 90",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax1.text(
                            x=0.88,
                            y=-1.03,
                            s=f"{npxg_p90:.2f}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax1.text(
                            x=0.83,
                            y=-1.3,
                            s="xGI per 90",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax1.text(
                            x=0.88,
                            y=-1.43,
                            s=f"{xgi_p90:.2f}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax2 = fig.add_axes([0.05, 0.3, 0.72, 0.45])
                        for spine in ax2.spines.values():
                            spine.set_visible(False)
                        ax2.set_xticks([])
                        ax2.set_yticks([])
                        ax2.set_facecolor(background_color2)

                        pitch = VerticalPitch(
                            pitch_type="opta",
                            half=True,
                            pitch_color=background_color2,
                            pad_bottom=0.5,
                            line_color="white",
                            linewidth=0.75,
                            axis=True,
                            label=True,
                        )

                        pitch.draw(ax=ax2)

                        for x in df.to_dict(orient="records"):
                            pitch.scatter(
                                x["X"],
                                x["Y"],
                                s=400 * x["xG"],
                                color=(
                                    "blue"
                                    if x["result"] == "Goal"
                                    and x["situation"] == "Penalty"
                                    else "violet"
                                    if x["result"] != "Goal"
                                    and x["situation"] == "Penalty"
                                    else "turquoise"
                                    if x["result"] == "Goal"
                                    and x["situation"] == "Freekick"
                                    else "yellow"
                                    if x["result"] == "SavedShot"
                                    else "red"
                                    if x["result"] == "Goal"
                                    else background_color2
                                ),
                                marker=(
                                    "s"
                                    if x["situation"] == "Penalty"
                                    else "^"
                                    if x["situation"] == "Freekick"
                                    else "o"
                                ),
                                ax=ax2,
                                alpha=0.6,
                                linewidth=0.8,
                                edgecolor="white",
                            )

                        ax3 = fig.add_axes([0, 0.2, 1, 0.05])
                        for spine in ax3.spines.values():
                            spine.set_visible(False)
                        ax3.set_xticks([])
                        ax3.set_yticks([])
                        ax3.set_facecolor(background_color)

                        ax3.text(
                            x=0.06,
                            y=1.8,
                            s="Total Shots",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.12,
                            y=1.4,
                            s=f"{number_of_shots}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.25,
                            y=1.8,
                            s="Total Goals",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.32,
                            y=1.4,
                            s=f"{number_of_goals}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.44,
                            y=1.8,
                            s="Total xG",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.48,
                            y=1.4,
                            s=f"{number_of_xg:.2f}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.6,
                            y=1.8,
                            s="xG per Shot",
                            fontsize=20,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.66,
                            y=1.4,
                            s=f"{xg_per_shot:.2f}",
                            fontsize=18,
                            fontproperties=font_props,
                            fontweight="bold",
                            color="white",
                            ha="left",
                        )

                        ax3.text(
                            x=0.29,
                            y=0.05,
                            s="Viz by @BetterThanMario | Created using https://shotmap.streamlit.app | Data: understat.com",
                            fontsize=10,
                            color="white",
                            alpha=0.7,
                        )

                        st.session_state.fig = fig
                        st.session_state.generate_plot = True

                        st.info(
                            "The shot map has been generated. Click on the Output tab to see the generated plot."
                        )

                        st.session_state.results_cache[cache_key] = st.session_state.fig

                    except Exception as e:
                        st.error(f"Error generating shot map: {str(e)}")
                        st.session_state.generate_plot = False

    elif button and season:
        st.warning("Please enter a player name first.", icon=":material/error:")

    elif button and input1:
        st.warning("Please enter a season first.", icon=":material/error:")

    elif button:
        st.warning(
            "Please enter a player name and season first.", icon=":material/error:"
        )

    if button:
        st.session_state.generate_plot = True

with tab2:
    st.header("Output")
    st.markdown(
        "Any doubts regarding the output generated? Or bored while waiting? Head over to the FAQ tab to learn more about the project."
    )

    st.subheader("Your Shot Map will be generated here:")

    if st.session_state.generate_plot and st.session_state.fig:
        st.pyplot(st.session_state.fig, use_container_width=False)
        file_name = f"{input1}_{season}_shot_map.png"

        buf = BytesIO()
        st.session_state.fig.savefig(buf, format="png", bbox_inches="tight", dpi=300)
        buf.seek(0)

        st.download_button(
            label="Download the Shot Map (PNG)",
            data=buf.getvalue(),
            file_name=file_name,
            mime="image/png",
        )

    else:
        st.info(
            "Please enter valid inputs in the Main tab and click 'Generate Plot' to see results here."
        )

with tab3:
    what_is_a_shot_map = """A shot map is a visual representation of a player's shots taken during a match or over a season. It typically shows the location of each shot on the pitch, along with additional information such as whether the shot was on target, off target, or resulted in a goal. Shot maps are useful for analyzing a player's shooting performance and understanding their scoring opportunities, primarily (but not limited to) useful for players in the attacking roles."""
    how_is_it_useful = """Shot maps are useful for analyzing a player's ability to finish and understanding their attacking output. It essentially is a graphical representation of the quality of scoring opportunities a player avails to himself. Keen data-loving fans and even the general public can use this to assist their own work or develop a deeper understanding about a players' scoring ability."""
    what_is_xg = """xG, or expected goals, is a metric used in football to assess the quality of scoring chances. It assigns a value to each shot based on various factors such as shot location, angle, type of chance, etc. The xG value represents the likelihood of a shot resulting in a goal, with higher values indicating a better goal-scoring chance. xG is useful for evaluating player performance and team attacking efficiency."""
    what_is_npxg = """npxG, or non-penalty expected goals, is a variant of the xG metric that excludes penalty kicks. It focuses solely on the quality of scoring chances from open play and set pieces, providing a clearer picture of a player's goal-scoring ability without the influence of penalties which tend to be shots with very high xG."""
    what_is_xgi = """xGI, or expected goal involvement, is a metric that combines a player's expected goals (xG) and expected assists (xA) into a single value. It measures a player's overall attacking contribution by considering both their goal-scoring opportunities and their creativity."""
    what_is_per90 = """Per 90 metrics refers to statistics that are normalized to a 90-minute match duration. It allows for fair comparisons between players or teams regardless of the number of minutes played. However, it is important to note that sometimes per 90 stats can be misleading if a player has played significantly fewer minutes than others, as these may not accurately reflect their overall performance."""
    what_are_the_circles = """The circles on the shot map represent the quality of the scoring chance. The size of the circle indicates the xG value of the shot, with larger circles representing higher xG values and vice versa. The colour of the circle indicates the result of the shot, such as a goal (red), saved shot (yellow), blocked/off target (colourless), penalty scored (blue square), penalty missed (pink square), and freekick scored (turquoise triangle)."""

    st.markdown("### Frequently Asked Questions (FAQ)")
    with st.expander("What is a shot map?"):
        st.write(what_is_a_shot_map)

    with st.expander("How can I use it?"):
        st.write(how_is_it_useful)

    with st.expander("What is xG?"):
        st.write(what_is_xg)

    with st.expander("What is npxG?"):
        st.write(what_is_npxg)

    with st.expander("What is xGI?"):
        st.write(what_is_xgi)

    with st.expander("Why are all the metrics in 'per 90'?"):
        st.write(what_is_per90)

    with st.expander("What does the size of the shape indicate?"):
        st.write(what_are_the_circles)

    st.markdown("---")
    st.markdown("""
    ## Shot Map Legend
    #### **Shapes**
    - **Dot Size**: Larger dots represent higher xG (expected goal) value chances
    - **Circle**: All shots taken in open play or from corners
    - **Square**: Penalty shots taken
    - **Triangle**: Free kick shots taken
    
    #### **Colours**
    - Red: Goal
    - Yellow: Saved shot
    - Blue: Penalty scored
    - Violet: Penalty missed
    - Turquoise: Free kick scored
    - Default: Blocked/missed shots

    #### **Stats Explained**
    - **xG (Expected Goals)**: Probability of scoring based on shot quality
    - **npxG**: Non-penalty expected goals
    - **xGI**: Expected goal involvement (xG + xA)
    - **xA**: Expected assists
        """)


st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.8em;'>
    By Anay Shukla | Data provided by Understat.com 
    </div>
    """,
    unsafe_allow_html=True,
)
