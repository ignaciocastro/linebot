const BOT_RE =
  /discordbot|twitterbot|facebookexternalhit|facebookcatalog|linkedinbot|slackbot|telegrambot|whatsapp|pinterestbot|embedly/i;

const EN_DESC = "Backup of the 2022 LINE promotional bot for volume two of TSHD";
const JA_DESC = "「光が死んだ夏」2巻の2022年LINEプロモーションボットのバックアップ";

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const ua = request.headers.get("user-agent") || "";
  const isBot = BOT_RE.test(ua);

  if (url.pathname === "/" && url.searchParams.has("m") && isBot) {
    const m = url.searchParams.get("m") || "";
    const lang = url.searchParams.get("lang") === "ja" ? "ja" : "en";
    if (/^[A-Za-z0-9_-]+$/.test(m)) {
      const target = new URL(`/m/${m}/${lang}.html`, url.origin);
      try {
        const res = await fetch(new Request(target.toString(), { headers: { "user-agent": ua } }));
        if (res.ok) {
          const headers = new Headers(res.headers);
          headers.set("content-type", "text/html; charset=UTF-8");
          headers.delete("content-length");
          return new Response(await res.text(), { status: 200, headers });
        }
      } catch (_) {
      }
    }
  }

  if (url.pathname === "/" && !url.searchParams.has("m") && isBot && url.searchParams.get("lang") === "ja") {
    try {
      const res = await fetch(new Request(url.origin + "/", { headers: { "user-agent": ua } }));
      if (res.ok) {
        const headers = new Headers(res.headers);
        headers.set("content-type", "text/html; charset=UTF-8");
        headers.delete("content-length");
        const html = (await res.text()).split(EN_DESC).join(JA_DESC);
        return new Response(html, { status: 200, headers });
      }
    } catch (_) {
    }
  }

  return context.next();
}
