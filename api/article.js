export const config = { runtime: 'edge' };

export default async function handler(req) {
  const SUPABASE_URL = process.env.SUPABASE_URL;
  const SUPABASE_KEY = process.env.SUPABASE_KEY;

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return new Response(JSON.stringify({ error: 'Missing env vars' }), {
      status: 500, headers: corsHeaders('application/json'),
    });
  }

  const { searchParams } = new URL(req.url);
  const id = searchParams.get('id');

  if (!id) {
    return new Response(JSON.stringify({ error: 'Missing id' }), {
      status: 400, headers: corsHeaders('application/json'),
    });
  }

  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/articles?id=eq.${id}&select=*&limit=1`,
      { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
    );
    const data = await res.json();
    const article = Array.isArray(data) ? data[0] : null;

    if (!article) {
      return new Response(JSON.stringify({ error: 'Not found' }), {
        status: 404, headers: corsHeaders('application/json'),
      });
    }

    return new Response(JSON.stringify(article), {
      status: 200, headers: corsHeaders('application/json'),
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500, headers: corsHeaders('application/json'),
    });
  }
}

function corsHeaders(contentType) {
  return {
    'Content-Type': contentType,
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'public, max-age=300',
  };
}
