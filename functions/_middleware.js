const BOT_RE =
  /discordbot|twitterbot|facebookexternalhit|facebookcatalog|linkedinbot|slackbot|telegrambot|whatsapp|pinterestbot|embedly/i;

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const ua = request.headers.get("user-agent") || "";

  if (url.pathname === "/" && url.searchParams.has("m") && BOT_RE.test(ua)) {
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

  return context.next();
}
