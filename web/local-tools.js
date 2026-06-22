(() => {
function isLocalDateTimeRequest(text) {
  const normalized = text.replace(/\s+/g, "").toLowerCase();
  if (!normalized) return false;
  if (
    /(何時|時間).{0,8}(から|まで|〜|～|終了|開始|受付|面会|営業時間|診療時間|開館|閉館)/.test(normalized) ||
    /(から|まで|〜|～).{0,8}(何時|時間)/.test(normalized) ||
    /(面会時間|営業時間|受付時間|診療時間|開館時間|閉館時間|予約時間|利用時間)/.test(normalized)
  ) {
    return false;
  }
  return (
    /(いま|今|現在|今の).{0,6}(時間|時刻|何時)|^(何時|いま何時|今何時|現在時刻|現在の時刻)$/.test(normalized) ||
    /(今日|本日|現在).{0,6}(日付|何日|曜日)|何曜日/.test(normalized) ||
    /^(time|date|today|whattime|whatday)\??$/i.test(normalized)
  );
}

function normalizeShortReply(text) {
  return text.replace(/[!！?？。、〜~ー－—\s]/g, "").toLowerCase();
}

function isCasualQuickReplyRequest(text) {
  const normalized = normalizeShortReply(text);
  if (normalized.length > 24) return false;
  return (
    /^(つかれた|疲れた|なんかつかれた|なんか疲れた|しんどい|ねむい|眠い|ねむ)$/.test(normalized) ||
    /^(わかった|了解|りょうかい|ok|おけ|なるほど|たしかに|そうだね|そうですね)$/.test(normalized) ||
    /^(ok|おけ)?(がんばる|頑張る)(ね|よ)?$/.test(normalized) ||
    /^(おそい|遅い|おそかった|遅かった|まだ|ながい|長い)$/.test(normalized)
  );
}

function localDateTimeAnswer(text) {
  const now = new Date();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "local";
  const date = new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(now);
  const weekday = new Intl.DateTimeFormat("ja-JP", { weekday: "long" }).format(now);
  const time = new Intl.DateTimeFormat("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(now);
  const normalized = text.replace(/\s+/g, "");
  if (/曜日/.test(normalized) && !/(時間|時刻|何時)/.test(normalized)) {
    return `今日は${date}（${weekday}）です。`;
  }
  if (/(日付|何日|today|date)/i.test(normalized) && !/(時間|時刻|何時|time)/i.test(normalized)) {
    return `今日は${date}（${weekday}）です。`;
  }
  return `現在時刻は ${date}（${weekday}） ${time}（${timeZone}）です。`;
}

window.GEMMA_LOCAL_TOOLS = {
  isCasualQuickReplyRequest,
  isLocalDateTimeRequest,
  localDateTimeAnswer,
  normalizeShortReply,
};
})();
