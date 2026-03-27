require('dotenv').config();
const express = require('express');
const { Client, middleware, validateSignature } = require('@line/bot-sdk');

const app = express();
const PORT = process.env.PORT || 3000;

const lineConfig = {
  channelSecret: process.env.LINE_CHANNEL_SECRET,
  channelAccessToken: process.env.LINE_CHANNEL_ACCESS_TOKEN,
};
const client = new Client(lineConfig);

// ─── 診断データ ────────────────────────────────────────────────
const QUESTIONS = [
  {
    text: 'Q1 / 7\n\nAIツール（ChatGPT・Claudeなど）を\n使ったことはありますか？',
    choices: [
      { label: '毎日のように使っている', score: 3 },
      { label: '週に数回使う', score: 2 },
      { label: 'たまに使う程度', score: 1 },
      { label: 'ほとんど使わない', score: 0 },
    ],
  },
  {
    text: 'Q2 / 7\n\n使っているAIツールはどれに近いですか？',
    choices: [
      { label: '複数ツールを使い分けている', score: 3 },
      { label: 'ChatGPT有料版を使っている', score: 2 },
      { label: '無料版のみ使っている', score: 1 },
      { label: 'まだ使ったことがない', score: 0 },
    ],
  },
  {
    text: 'Q3 / 7\n\nAIを仕事・ビジネスに活用していますか？',
    choices: [
      { label: 'メイン業務に組み込んでいる', score: 3 },
      { label: '補助的に活用している', score: 2 },
      { label: '試したことはある', score: 1 },
      { label: 'プライベートのみ／未使用', score: 0 },
    ],
  },
  {
    text: 'Q4 / 7\n\nAIプロンプトを自分でカスタマイズできますか？',
    choices: [
      { label: '目的に合わせて自在に書ける', score: 3 },
      { label: 'テンプレを参考に調整できる', score: 2 },
      { label: 'コピペで使っている', score: 1 },
      { label: 'プロンプトって何…？', score: 0 },
    ],
  },
  {
    text: 'Q5 / 7\n\nAIを使って業務を効率化・自動化できていますか？',
    choices: [
      { label: '複数の業務を自動化できた', score: 3 },
      { label: '1〜2つの業務で活用中', score: 2 },
      { label: 'やってみたいけどまだ', score: 1 },
      { label: '自動化は考えていない', score: 0 },
    ],
  },
  {
    text: 'Q6 / 7\n\nAIの最新情報をキャッチアップしていますか？',
    choices: [
      { label: '週1以上チェックしている', score: 2 },
      { label: '気になったときに調べる', score: 1 },
      { label: 'あまり追っていない', score: 0 },
    ],
  },
  {
    text: 'Q7 / 7（最後の質問です！）\n\nAIをビジネスの収益につなげていますか？',
    choices: [
      { label: 'すでに収益化できている', score: 3 },
      { label: '収益化に向けて動いている', score: 2 },
      { label: '興味はあるけどまだ', score: 1 },
      { label: '収益化は考えていない', score: 0 },
    ],
  },
];

const LEVELS = [
  {
    min: 0, max: 4,
    badge: 'LEVEL 1', emoji: '🌱',
    title: 'AI入門者',
    color: '#FF6B6B',
    summary: 'AIとの出会いはこれから！\nまずは基礎から一緒に学んでいきましょう🎓',
    advice: 'ChatGPTの無料版に登録して、まず「挨拶」だけしてみてください。それが最初の一歩！',
    potential: '月10〜20時間の時間削減が期待できます',
    cta: '✨ 無料相談でAI活用を始めよう',
  },
  {
    min: 5, max: 9,
    badge: 'LEVEL 2', emoji: '🔥',
    title: 'AI見習い',
    color: '#FFA94D',
    summary: '使い始めてはいるけど\nまだ「なんとなく」の段階ですね！',
    advice: 'プロンプトの型を覚えるだけで出力品質が劇的にアップ！「役割設定＋指示」の書き方を学びましょう。',
    potential: '正しく使えば月20〜30時間削減が見えてきます',
    cta: '🚀 無料相談でAI活用を加速させよう',
  },
  {
    min: 10, max: 14,
    badge: 'LEVEL 3', emoji: '⚡',
    title: 'AI活用中級者',
    color: '#51CF66',
    summary: 'かなり使いこなしてきてる！\nあとは「仕組み化」が次のステップです💪',
    advice: '複数ツールを連携させる「AI業務フロー」を設計しましょう。時間が一気に生まれます。',
    potential: 'フロー構築で月30〜50時間削減＋収益アップのチャンスがあります',
    cta: '💡 無料相談でAI仕組み化を設計しよう',
  },
  {
    min: 15, max: 99,
    badge: 'LEVEL 4', emoji: '👑',
    title: 'AIマスター',
    color: '#339AF0',
    summary: 'すごい！AIをビジネスレベルで\n使いこなしていますね✨',
    advice: 'あなたのAI活用ノウハウを商品化・コンテンツ化することで、さらに大きな収益が生まれます。',
    potential: 'ノウハウのパッケージ化でスケールアップ。収益倍増も現実的です',
    cta: '🌟 無料相談で次のステージを目指そう',
  },
];

function getLevel(score) {
  return LEVELS.find(l => score >= l.min && score <= l.max) || LEVELS[0];
}

// ─── セッション管理（メモリ）──────────────────────────────────
// { userId: { step: 0, score: 0 } }
const sessions = new Map();

function getSession(userId) {
  if (!sessions.has(userId)) {
    sessions.set(userId, { step: 0, score: 0 });
  }
  return sessions.get(userId);
}

function resetSession(userId) {
  sessions.set(userId, { step: 0, score: 0 });
}

// ─── メッセージ生成 ────────────────────────────────────────────
function makeQuestionMessage(q) {
  return {
    type: 'text',
    text: q.text,
    quickReply: {
      items: q.choices.map(c => ({
        type: 'action',
        action: {
          type: 'postback',
          label: c.label,
          data: `score=${c.score}`,
          displayText: c.label,
        },
      })),
    },
  };
}

function makeResultFlexMessage(score, lv) {
  const maxScore = 17;
  const pct = Math.round((score / maxScore) * 100);

  return {
    type: 'flex',
    altText: `診断結果：${lv.badge} ${lv.title}（${score}/${maxScore}点）`,
    contents: {
      type: 'bubble',
      size: 'mega',
      header: {
        type: 'box',
        layout: 'vertical',
        contents: [
          {
            type: 'box',
            layout: 'horizontal',
            contents: [
              {
                type: 'text',
                text: lv.badge,
                size: 'xs',
                weight: 'bold',
                color: '#ffffff',
                align: 'center',
              },
            ],
            backgroundColor: lv.color,
            paddingAll: '6px',
            cornerRadius: '20px',
            width: '80px',
          },
          { type: 'text', text: lv.emoji, size: 'xxl', align: 'center', margin: 'md' },
          { type: 'text', text: lv.title, weight: 'bold', size: 'xl', align: 'center', margin: 'sm' },
          {
            type: 'text',
            text: lv.summary,
            size: 'sm',
            color: '#555555',
            align: 'center',
            wrap: true,
            margin: 'sm',
          },
        ],
        paddingAll: '20px',
        backgroundColor: '#f8f8f8',
      },
      body: {
        type: 'box',
        layout: 'vertical',
        contents: [
          // スコアバー
          {
            type: 'box',
            layout: 'vertical',
            contents: [
              {
                type: 'box',
                layout: 'horizontal',
                contents: [
                  { type: 'text', text: 'AI活用スコア', size: 'xs', color: '#888888' },
                  {
                    type: 'text',
                    text: `${score} / ${maxScore}点`,
                    size: 'xs',
                    color: '#333333',
                    weight: 'bold',
                    align: 'end',
                  },
                ],
              },
              {
                type: 'box',
                layout: 'vertical',
                contents: [
                  {
                    type: 'box',
                    layout: 'vertical',
                    contents: [],
                    backgroundColor: lv.color,
                    height: '10px',
                    cornerRadius: '5px',
                    flex: pct,
                  },
                  {
                    type: 'box',
                    layout: 'vertical',
                    contents: [],
                    flex: 100 - pct,
                  },
                ],
                layout: 'horizontal',
                backgroundColor: '#eeeeee',
                height: '10px',
                cornerRadius: '5px',
                margin: 'sm',
              },
            ],
            margin: 'md',
          },
          { type: 'separator', margin: 'lg' },
          // アドバイス
          {
            type: 'box',
            layout: 'vertical',
            contents: [
              {
                type: 'box',
                layout: 'horizontal',
                contents: [
                  { type: 'text', text: '🎯', size: 'sm' },
                  {
                    type: 'text',
                    text: '今すぐできること',
                    size: 'sm',
                    weight: 'bold',
                    color: '#333333',
                    margin: 'sm',
                  },
                ],
                alignItems: 'center',
              },
              {
                type: 'text',
                text: lv.advice,
                size: 'sm',
                color: '#555555',
                wrap: true,
                margin: 'sm',
              },
            ],
            margin: 'lg',
          },
          {
            type: 'box',
            layout: 'vertical',
            contents: [
              {
                type: 'box',
                layout: 'horizontal',
                contents: [
                  { type: 'text', text: '⚡', size: 'sm' },
                  {
                    type: 'text',
                    text: 'AI化で期待できる変化',
                    size: 'sm',
                    weight: 'bold',
                    color: '#333333',
                    margin: 'sm',
                  },
                ],
                alignItems: 'center',
              },
              {
                type: 'text',
                text: lv.potential,
                size: 'sm',
                color: '#555555',
                wrap: true,
                margin: 'sm',
              },
            ],
            margin: 'lg',
            backgroundColor: '#f0fff4',
            cornerRadius: '10px',
            paddingAll: '12px',
          },
        ],
        paddingAll: '20px',
      },
      footer: {
        type: 'box',
        layout: 'vertical',
        contents: [
          {
            type: 'button',
            action: {
              type: 'uri',
              label: lv.cta,
              uri: 'https://lin.ee/XuKb1sK',
            },
            style: 'primary',
            color: '#06C755',
            height: 'sm',
          },
          {
            type: 'text',
            text: '※ 無料個別相談はLINEで受け付けています',
            size: 'xxs',
            color: '#aaaaaa',
            align: 'center',
            margin: 'sm',
          },
        ],
        paddingAll: '16px',
      },
    },
  };
}

// ─── イベントハンドラ ──────────────────────────────────────────
async function handleEvent(event) {
  const userId = event.source.userId;

  // ── テキストメッセージ
  if (event.type === 'message' && event.message.type === 'text') {
    const text = event.message.text.trim();

    // 診断スタートキーワード
    if (text === '診断' || text === 'AI診断' || text === 'スタート' || text === '診断スタート') {
      resetSession(userId);
      await client.replyMessage(event.replyToken, [
        {
          type: 'text',
          text: 'こんにちは！🤖\nあいかのAI活用レベル診断Botです✨\n\n7つの質問であなたのAI活用レベルを診断します！\nすべてタップで答えられるので、2〜3分で完了します😊\n\nでは早速はじめましょう！',
        },
        makeQuestionMessage(QUESTIONS[0]),
      ]);
      const session = getSession(userId);
      session.step = 1;
      return;
    }

    // 診断中でない場合のデフォルト返信
    const session = getSession(userId);
    if (session.step === 0) {
      await client.replyMessage(event.replyToken, {
        type: 'text',
        text: '「診断スタート」と送ると\n無料AI活用レベル診断ができます！🤖\n\nぜひ試してみてください✨',
      });
    }
    return;
  }

  // ── ポストバック（選択肢タップ）
  if (event.type === 'postback') {
    const session = getSession(userId);
    const params = new URLSearchParams(event.postback.data);
    const score = parseInt(params.get('score') || '0', 10);

    session.score += score;
    const nextStep = session.step; // 現在のstepが次の質問インデックス

    if (nextStep < QUESTIONS.length) {
      // 次の質問を送信
      await client.replyMessage(event.replyToken, makeQuestionMessage(QUESTIONS[nextStep]));
      session.step++;
    } else {
      // 診断完了 → 結果表示
      const lv = getLevel(session.score);
      await client.replyMessage(event.replyToken, [
        {
          type: 'text',
          text: `診断完了です！🎉\nあなたのスコアは ${session.score}/17点でした！\n\n結果をお届けします👇`,
        },
        makeResultFlexMessage(session.score, lv),
      ]);
      resetSession(userId);
    }
    return;
  }
}

// ─── Webhook エンドポイント ────────────────────────────────────
app.post('/webhook', middleware(lineConfig), (req, res) => {
  Promise.all(req.body.events.map(handleEvent))
    .then(() => res.status(200).json({ status: 'ok' }))
    .catch(err => {
      console.error(err);
      res.status(500).end();
    });
});

// ヘルスチェック
app.get('/', (req, res) => res.send('AI診断Bot 稼働中 ✅'));

app.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`);
});
