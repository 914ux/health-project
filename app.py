import os
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask, render_template, request, session

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# ※あなたの書き方を尊重（直書きのまま）。本来は genai.configure(api_key=GOOGLE_API_KEY) を推奨
genai.configure(api_key='AIzaSyCr-oSI-fY7gCVQaIYSdtj9LAxUXyjLgMY')

# 起動時に総評コメントを一度生成（失敗時はフォールバック）
try:
    gemini_pro = genai.GenerativeModel("models/gemini-1.5-flash")
    _prompt = "健康に関する総合評価コメントを書いてください"
    _resp = gemini_pro.generate_content(_prompt)
    AI_COMMENT_ON_BOOT = (_resp.text or "").strip() or "全体として良い取り組みです。小さな改善を継続しましょう。"
except Exception:
    AI_COMMENT_ON_BOOT = "全体として良い取り組みです。小さな改善を継続しましょう。"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

# 目安の平均睡眠時間（Jinjaでも参照できるように登録）
AVERAGE_SLEEP = 7.0
app.jinja_env.globals.update(AVERAGE_SLEEP=AVERAGE_SLEEP)

# ---- ヘルパ ----
def _to_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0

def kcal_base_per_day(sex: str, weight_kg: float) -> int:
    """1日の簡易目安カロリー：男性=30kcal/kg, 女性=26kcal/kg"""
    base = (30.0 if sex == "male" else 26.0) * float(weight_kg or 0)
    return int(round(base))

# ============ ルーティング ============

@app.route("/")
def index():
    # いきなり1枚目を描画
    return render_template("body.html")

# 1. 体重・年齢・性別 → 2. 朝ごはん
@app.route("/body", methods=["GET", "POST"])
def body():
    if request.method == "POST":
        session["age"] = request.form.get("age", "").strip()
        session["sex"] = request.form.get("sex", "male")
        session["weight"] = request.form.get("weight", "").strip()

        sex = session.get("sex", "male")
        weight = _to_float(session.get("weight", 0))
        kcal_target = kcal_base_per_day(sex, weight)
        kcal_breakfast = int(round(kcal_target * 0.25))

        # 次のページ(2枚目)を“その場で描画”
        return render_template("food.html",
                               kcal_target=kcal_target,
                               kcal_breakfast=kcal_breakfast)
    # GET直アクセス時
    return render_template("body.html")

# 2. 朝ごはん → 3. 睡眠
@app.route("/food", methods=["GET", "POST"])
def food():
    sex = session.get("sex", "male")
    weight = _to_float(session.get("weight", 0))
    kcal_target = kcal_base_per_day(sex, weight)
    kcal_breakfast = int(round(kcal_target * 0.25))

    if request.method == "POST":
        session["breakfast"] = request.form.get("breakfast", "no")
        # 次のページ(3枚目)を“その場で描画”
        return render_template("sleep.html")
    return render_template("food.html", kcal_target=kcal_target, kcal_breakfast=kcal_breakfast)

# 3. 睡眠（判定）→ 5. 運動
@app.route("/sleep", methods=["GET", "POST"])
def sleep():
    result = None
    advice = None

    if request.method == "POST":
        try:
            sleep_hours = float(request.form["sleep_hours"])
            session["sleep_hours"] = sleep_hours

            diff = round(sleep_hours - AVERAGE_SLEEP, 1)
            if diff > 0:
                result = f"平均より {diff:.1f} 時間多く眠りました（プラス）"
                advice = "よく眠れています。この調子で継続しましょう。"
            elif diff < 0:
                result = f"平均より {abs(diff):.1f} 時間少なく眠りました（マイナス）"
                advice = "目安は7時間。+30分の早寝など小さな改善から。"
            else:
                result = "平均と同じ睡眠時間です。"
                advice = "安定した睡眠は体調管理の土台です。"

            session["sleep_result"] = result
            session["sleep_advice"] = advice

            # 次のページ(5枚目)を“その場で描画”
            return render_template("active.html", sleep_result=result)

        except ValueError:
            result = "数値で入力してください。"
            return render_template("sleep.html", result=result)

    # GET直アクセス or 初期表示
    return render_template("sleep.html", result=result)

# 5. 昨日の運動 → 6. まとめ
@app.route("/active", methods=["GET", "POST"])
def active():
    if request.method == "POST":
        h_muscle = request.form.get("h_muscle", "0")
        h_run    = request.form.get("h_run", "0")
        h_walk   = request.form.get("h_walk", "0")
        h_other  = request.form.get("h_other", "0")

        # 分換算（ざっくり強度係数）
        minutes_done = (
            _to_float(h_walk)  * 60 * 0.8 +
            _to_float(h_muscle)* 60 * 1.0 +
            _to_float(h_run)   * 60 * 1.5 +
            _to_float(h_other) * 60 * 1.0
        )
        recommended_minutes = 30
        did_enough = minutes_done >= recommended_minutes

        # 朝食・カロリー計算
        sex = session.get("sex", "male")
        weight = _to_float(session.get("weight", 0))
        kcal_target = kcal_base_per_day(sex, weight)
        kcal_breakfast = int(round(kcal_target * 0.25))
        breakfast_yes = (session.get("breakfast", "no") == "yes")

        # 起動時に生成したAIコメントを使用（失敗時は既にフォールバック済み）
        ai_comment = AI_COMMENT_ON_BOOT

        # 6枚目を“その場で描画”
        return render_template(
            "comment.html",
            recommended_minutes=recommended_minutes,
            did_enough=did_enough,
            kcal_target=kcal_target,
            kcal_breakfast=kcal_breakfast,
            breakfast_yes=breakfast_yes,
            ai_comment=ai_comment
        )

    # GET直アクセス時
    return render_template("active.html")

if __name__ == "__main__":
    app.run(debug=True)
