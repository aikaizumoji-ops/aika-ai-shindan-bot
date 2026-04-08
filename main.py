import os
import hashlib
import hmac
import base64
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import urllib.request
from datetime import datetime, timedelta

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_API = "https://api.line.me/v2/bot/message/reply"

# ─── 診断データ ────────────────────────────────────────────────
QUESTIONS = [
    {
        "text": "Q1 / 7\n\nAIツール（ChatGPT・Claudeなど）を\n使ったことはありますか？",
        "choices": [
            {"label": "毎日のように使っている", "score": 3},
            {"label": "週に数回使う", "score": 2},
            {"label": "たまに使う程度", "score": 1},
            {"label": "ほとんど使わない", "score": 0},
        ],
    },
    {
        "text": "Q2 / 7\n\n使っているAIツールはどれに近いですか？",
        "choices": [
            {"label": "複数ツールを使い分けている", "score": 3},
            {"label": "ChatGPT有料版を使っている", "score": 2},
            {"label": "無料版のみ使っている", "score": 1},
            {"label": "まだ使ったことがない", "score": 0},
        ],
    },
    {
        "text": "Q3 / 7\n\nAIを仕事・ビジネスに活用していますか？",
        "choices": [
            {"label": "メイン業務に組み込んでいる", "score": 3},
            {"label": "補助的に活用している", "score": 2},
            {"label": "試したことはある", "score": 1},
            {"label": "プライベートのみ／未使用", "score": 0},
        ],
    },
    {
        "text": "Q4 / 7\n\nAIプロンプトを自分でカスタマイズできますか？",
        "choices": [
            {"label": "目的に合わせて自在に書ける", "score": 3},
            {"label": "テンプレを参考に調整できる", "score": 2},
            {"label": "コピペで使っている", "score": 1},
            {"label": "プロンプトって何…？", "score": 0},
        ],
    },
    {
        "text": "Q5 / 7\n\nAIを使って業務を効率化・自動化できていますか？",
        "choices": [
            {"label": "複数の業務を自動化できた", "score": 3},
            {"label": "1〜2つの業務で活用中", "score": 2},
            {"label": "やってみたいけどまだ", "score": 1},
            {"label": "自動化は考えていない", "score": 0},
        ],
    },
    {
        "text": "Q6 / 7\n\nAIの最新情報をキャッチアップしていますか？",
        "choices": [
            {"label": "週1以上チェックしている", "score": 2},
            {"label": "気になったときに調べる", "score": 1},
            {"label": "あまり追っていない", "score": 0},
        ],
    },
    {
        "text": "Q7 / 7（最後の質問です！）\n\nAIをビジネスの収益につなげていますか？",
        "choices": [
            {"label": "すでに収益化できている", "score": 3},
            {"label": "収益化に向けて動いている", "score": 2},
            {"label": "興味はあるけどまだ", "score": 1},
            {"label": "収益化は考えていない", "score": 0},
        ],
    },
]

LEVELS = [
    {
        "min": 0, "max": 4,
        "badge": "LEVEL 1", "emoji": "🌱", "title": "AI入門者", "color": "#FF6B6B",
        "summary": "AIとの出会いはこれから！まずは基礎から一緒に学んでいきましょう🎓",
        "advice": "ChatGPTの無料版に登録して、まず「挨拶」だけしてみてください。それが最初の一歩！",
        "potential": "月10〜20時間の時間削減が期待できます",
        "cta": "✨ 無料相談でAI活用を始めよう",
    },
    {
        "min": 5, "max": 9,
        "badge": "LEVEL 2", "emoji": "🔥", "title": "AI見習い", "color": "#FFA94D",
        "summary": "使い始めてはいるけど、まだ「なんとなく」の段階ですね！",
        "advice": "プロンプトの型を覚えるだけで出力品質が劇的にアップ！「役割設定＋指示」の書き方を学びましょう。",
        "potential": "正しく使えば月20〜30時間削減が見えてきます",
        "cta": "🚀 無料相談でAI活用を加速させよう",
    },
    {
        "min": 10, "max": 14,
        "badge": "LEVEL 3", "emoji": "⚡", "title": "AI活用中級者", "color": "#51CF66",
        "summary": "かなり使いこなしてきてる！あとは「仕組み化」が次のステップです💪",
        "advice": "複数ツールを連携させる「AI業務フロー」を設計しましょう。時間が一気に生まれます。",
        "potential": "フロー構築で月30〜50時間削減＋収益アップのチャンスがあります",
        "cta": "💡 無料相談でAI仕組み化を設計しよう",
    },
    {
        "min": 15, "max": 99,
        "badge": "LEVEL 4", "emoji": "👑", "title": "AIマスター", "color": "#339AF0",
        "summary": "すごい！AIをビジネスレベルで使いこなしていますね✨",
        "advice": "あなたのAI活用ノウハウを商品化・コンテンツ化することで、さらに大きな収益が生まれます。",
        "potential": "ノウハウのパッケージ化でスケールアップ。収益倍増も現実的です",
        "cta": "🌟 無料相談で次のステージを目指そう",
    },
]

def get_level(score):
    for lv in LEVELS:
        if lv["min"] <= score <= lv["max"]:
            return lv
    return LEVELS[0]

# ─── 無料相談 予約データ ─────────────────────────────────────────
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

TIME_SLOTS = [
    "10:00〜11:00",
    "11:00〜12:00",
    "12:00〜13:00",
    "13:00〜14:00",
    "14:00〜15:00",
    "15:00〜16:00",
    "19:00〜20:00",
    "20:00〜21:00",
]

# CEO通知用 — 予約をPush通知するユーザーID（LINE Developersで確認）
CEO_USER_ID = os.environ.get("CEO_LINE_USER_ID", "")
LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"

def push_message(to_user_id, messages):
    """Reply APIではなくPush APIで任意のタイミングに送信"""
    if not to_user_id:
        return
    if not isinstance(messages, list):
        messages = [messages]
    body = json.dumps({"to": to_user_id, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        LINE_PUSH_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
        method="POST",
    )
    try:
        res = urllib.request.urlopen(req)
        print(f"[PUSH OK] status={res.status}", flush=True)
    except Exception as e:
        print(f"[PUSH ERROR] {e}", flush=True)

def get_next_7days():
    """直近7日間の日付リストを生成（JST想定）"""
    today = datetime.now() + timedelta(hours=9)  # UTC→JST
    days = []
    for i in range(1, 8):
        d = today + timedelta(days=i)
        wd = WEEKDAY_JP[d.weekday()]
        label = f"{d.month}/{d.day}（{wd}）"
        value = d.strftime("%Y-%m-%d")
        days.append({"label": label, "value": value})
    return days

def make_date_picker_msg():
    """日付選択のQuick Replyメッセージ"""
    days = get_next_7days()
    items = [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": d["label"],
                "data": f"booking_date={d['value']}",
                "displayText": d["label"],
            },
        }
        for d in days
    ]
    return {
        "type": "text",
        "text": "📅 ご都合の良い日をお選びください",
        "quickReply": {"items": items},
    }

def make_time_picker_msg():
    """時間帯選択のQuick Replyメッセージ"""
    items = [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": slot,
                "data": f"booking_time={slot}",
                "displayText": slot,
            },
        }
        for slot in TIME_SLOTS
    ]
    return {
        "type": "text",
        "text": "⏰ ご希望の時間帯をお選びください",
        "quickReply": {"items": items},
    }

def make_booking_confirm_flex(date_str, time_slot):
    """予約確定のFlexメッセージ"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    wd = WEEKDAY_JP[d.weekday()]
    display_date = f"{d.year}年{d.month}月{d.day}日（{wd}）"
    return {
        "type": "flex",
        "altText": f"無料相談のご予約：{display_date} {time_slot}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "✅ ご予約を受け付けました", "weight": "bold", "size": "lg", "align": "center", "color": "#ffffff"},
                ],
                "backgroundColor": "#06C755",
                "paddingAll": "16px",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "無料相談", "weight": "bold", "size": "xl", "align": "center", "margin": "md"},
                    {"type": "separator", "margin": "lg"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📅 日時", "size": "sm", "color": "#888888", "flex": 2},
                                    {"type": "text", "text": display_date, "size": "sm", "weight": "bold", "color": "#333333", "flex": 5, "wrap": True},
                                ],
                                "margin": "lg",
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⏰ 時間", "size": "sm", "color": "#888888", "flex": 2},
                                    {"type": "text", "text": time_slot, "size": "sm", "weight": "bold", "color": "#333333", "flex": 5},
                                ],
                                "margin": "md",
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "💻 形式", "size": "sm", "color": "#888888", "flex": 2},
                                    {"type": "text", "text": "オンライン（Zoom）", "size": "sm", "weight": "bold", "color": "#333333", "flex": 5},
                                ],
                                "margin": "md",
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "uri",
                                    "label": "🔗 Zoomに参加する",
                                    "uri": "https://us02web.zoom.us/j/3751503981?pwd=RGRYdnlPTENNbkZlQUdOdTBQRENVQT09",
                                },
                                "style": "primary",
                                "color": "#2D8CFF",
                                "height": "sm",
                                "margin": "lg",
                            },
                        ],
                        "backgroundColor": "#f8f8f8",
                        "cornerRadius": "10px",
                        "paddingAll": "16px",
                        "margin": "lg",
                    },
                    {"type": "text", "text": "確認のご連絡をお送りしますので\n少々お待ちください😊", "size": "sm", "color": "#555555", "wrap": True, "align": "center", "margin": "lg"},
                ],
                "paddingAll": "20px",
            },
        },
    }

# ─── セッション（メモリ）──────────────────────────────────────
sessions = {}  # {user_id: {"step": int, "score": int, "mode": str, "booking_date": str}}

def get_session(user_id):
    if user_id not in sessions:
        sessions[user_id] = {"step": 0, "score": 0, "mode": "", "booking_date": ""}
    return sessions[user_id]

def reset_session(user_id):
    sessions[user_id] = {"step": 0, "score": 0, "mode": "", "booking_date": ""}

# ─── LINE API ─────────────────────────────────────────────────
def reply(reply_token, messages):
    if not isinstance(messages, list):
        messages = [messages]
    body = json.dumps({"replyToken": reply_token, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        LINE_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
        method="POST",
    )
    try:
        res = urllib.request.urlopen(req)
        print(f"[REPLY OK] status={res.status}", flush=True)
    except Exception as e:
        print(f"[REPLY ERROR] {e}", flush=True)

def make_question_msg(q):
    items = [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": c["label"],
                "data": f"score={c['score']}",
                "displayText": c["label"],
            },
        }
        for c in q["choices"]
    ]
    return {"type": "text", "text": q["text"], "quickReply": {"items": items}}

def make_result_flex(score, lv):
    max_score = 17
    pct = round((score / max_score) * 100)
    return {
        "type": "flex",
        "altText": f"診断結果：{lv['badge']} {lv['title']}（{score}/{max_score}点）",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [{"type": "text", "text": lv["badge"], "size": "xs", "weight": "bold", "color": "#ffffff", "align": "center"}],
                        "backgroundColor": lv["color"],
                        "paddingAll": "6px",
                        "cornerRadius": "20px",
                        "width": "80px",
                    },
                    {"type": "text", "text": lv["emoji"], "size": "xxl", "align": "center", "margin": "md"},
                    {"type": "text", "text": lv["title"], "weight": "bold", "size": "xl", "align": "center", "margin": "sm"},
                    {"type": "text", "text": lv["summary"], "size": "sm", "color": "#555555", "align": "center", "wrap": True, "margin": "sm"},
                ],
                "paddingAll": "20px",
                "backgroundColor": "#f8f8f8",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "AI活用スコア", "size": "xs", "color": "#888888"},
                                    {"type": "text", "text": f"{score} / {max_score}点", "size": "xs", "color": "#333333", "weight": "bold", "align": "end"},
                                ],
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "box", "layout": "vertical", "contents": [], "backgroundColor": lv["color"], "height": "10px", "cornerRadius": "5px", "flex": pct},
                                    {"type": "box", "layout": "vertical", "contents": [], "flex": max(1, 100 - pct)},
                                ],
                                "backgroundColor": "#eeeeee",
                                "height": "10px",
                                "cornerRadius": "5px",
                                "margin": "sm",
                            },
                        ],
                        "margin": "md",
                    },
                    {"type": "separator", "margin": "lg"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🎯", "size": "sm"},
                                    {"type": "text", "text": "今すぐできること", "size": "sm", "weight": "bold", "color": "#333333", "margin": "sm"},
                                ],
                                "alignItems": "center",
                            },
                            {"type": "text", "text": lv["advice"], "size": "sm", "color": "#555555", "wrap": True, "margin": "sm"},
                        ],
                        "margin": "lg",
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⚡", "size": "sm"},
                                    {"type": "text", "text": "AI化で期待できる変化", "size": "sm", "weight": "bold", "color": "#333333", "margin": "sm"},
                                ],
                                "alignItems": "center",
                            },
                            {"type": "text", "text": lv["potential"], "size": "sm", "color": "#555555", "wrap": True, "margin": "sm"},
                        ],
                        "margin": "lg",
                        "backgroundColor": "#f0fff4",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                    },
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {"type": "uri", "label": lv["cta"], "uri": "https://lin.ee/XuKb1sK"},
                        "style": "primary",
                        "color": "#06C755",
                        "height": "sm",
                    },
                    {"type": "text", "text": "※ 無料個別相談はLINEで受け付けています", "size": "xxs", "color": "#aaaaaa", "align": "center", "margin": "sm"},
                ],
                "paddingAll": "16px",
            },
        },
    }

# ─── イベント処理 ─────────────────────────────────────────────
def handle_event(event):
    user_id = event.get("source", {}).get("userId", "")
    reply_token = event.get("replyToken", "")
    event_type = event.get("type", "")

    if event_type == "message" and event.get("message", {}).get("type") == "text":
        text = event["message"]["text"].strip()
        session = get_session(user_id)

        if text in ["無料相談", "予約", "相談"]:
            reset_session(user_id)
            session = get_session(user_id)
            session["mode"] = "booking"
            reply(reply_token, [
                {"type": "text", "text": "無料相談にご興味いただき\nありがとうございます😊\n\n宅配便の時間指定のように\nタップで日時をお選びください📦✨"},
                make_date_picker_msg(),
            ])

        elif text in ["診断", "AI診断", "スタート", "診断スタート"]:
            reset_session(user_id)
            session = get_session(user_id)
            session["mode"] = "quiz"
            reply(reply_token, [
                {"type": "text", "text": "こんにちは！🤖\nあいかのAI活用レベル診断Botです✨\n\n7つの質問であなたのAI活用レベルを診断します！\nすべてタップで答えられるので、2〜3分で完了します😊\n\nでは早速はじめましょう！"},
                make_question_msg(QUESTIONS[0]),
            ])
            session["step"] = 1
        else:
            if session["step"] == 0 and session.get("mode", "") == "":
                reply(reply_token, [
                    {"type": "text", "text": "ご登録ありがとうございます🌿\n\n【環境再生型造園 オンライン実践講座】は\n現在準備中です。\n\n🚧 Coming Soon 🚧\n\n講座の詳細・募集開始のご案内は\nこちらのLINEで最速でお届けします。\n\n楽しみにお待ちください✨"},
                    {"type": "text", "text": "💡 AI活用レベル診断もできます！\n「診断スタート」と送ってみてください🤖"},
                ])

    elif event_type == "postback":
        session = get_session(user_id)
        data = parse_qs(event["postback"]["data"])

        # ─── 無料相談：日付選択 ───
        if "booking_date" in data:
            selected_date = data["booking_date"][0]
            session["booking_date"] = selected_date
            session["mode"] = "booking"
            reply(reply_token, make_time_picker_msg())

        # ─── 無料相談：時間帯選択 → 予約確定 ───
        elif "booking_time" in data:
            selected_time = data["booking_time"][0]
            booking_date = session.get("booking_date", "")
            if not booking_date:
                reply(reply_token, {"type": "text", "text": "もう一度「無料相談」と送ってください🙏"})
                reset_session(user_id)
                return

            # ユーザーに確認メッセージ
            reply(reply_token, make_booking_confirm_flex(booking_date, selected_time))

            # CEOに通知（Push API）
            d = datetime.strptime(booking_date, "%Y-%m-%d")
            wd = WEEKDAY_JP[d.weekday()]
            display_date = f"{d.year}年{d.month}月{d.day}日（{wd}）"
            push_message(CEO_USER_ID, {
                "type": "text",
                "text": f"📩 新しい無料相談の予約が入りました！\n\n👤 ユーザーID: {user_id[:8]}...\n📅 日時: {display_date}\n⏰ 時間: {selected_time}\n\n確認連絡をお願いします🙏",
            })

            print(f"[BOOKING] user={user_id[:8]} date={booking_date} time={selected_time}", flush=True)
            reset_session(user_id)

        # ─── 診断クイズ：回答処理 ───
        elif "score" in data:
            score = int(data.get("score", ["0"])[0])
            session["score"] += score
            next_step = session["step"]

            if next_step < len(QUESTIONS):
                reply(reply_token, make_question_msg(QUESTIONS[next_step]))
                session["step"] += 1
            else:
                lv = get_level(session["score"])
                reply(reply_token, [
                    {"type": "text", "text": f"診断完了です！🎉\nあなたのスコアは {session['score']}/17点でした！\n\n結果をお届けします👇"},
                    make_result_flex(session["score"], lv),
                ])
                reset_session(user_id)

# ─── HTTP サーバー ────────────────────────────────────────────
def verify_signature(body, signature):
    hash_ = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(hash_).decode("utf-8") == signature

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logs

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AI Bot running OK")

    def do_POST(self):
        print(f"[POST] path={self.path}", flush=True)
        if self.path not in ("/webhook", "/callback"):
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        signature = self.headers.get("X-Line-Signature", "")
        print(f"[SIG] len={len(body)} sig={signature[:20]}...", flush=True)

        if not verify_signature(body, signature):
            print(f"[403] signature mismatch", flush=True)
            self.send_response(403)
            self.end_headers()
            return

        try:
            data = json.loads(body.decode("utf-8"))
            events = data.get("events", [])
            print(f"[EVENTS] count={len(events)}", flush=True)
            for event in events:
                print(f"[EVENT] type={event.get('type')} userId={event.get('source',{}).get('userId','?')[:8]}", flush=True)
                handle_event(event)
        except Exception as e:
            print(f"[ERROR] {e}", flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"✅ Server running on port {port}")
    server.serve_forever()
