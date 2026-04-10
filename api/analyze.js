export const config = { runtime: 'edge' };

export default async function handler(req) {
  // Chỉ cho POST
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders() });
  }
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: corsHeaders('application/json'),
    });
  }

  const GROQ_KEY = process.env.GROQ_KEY;
  if (!GROQ_KEY) {
    return new Response(JSON.stringify({ error: 'GROQ_KEY not configured' }), {
      status: 500,
      headers: corsHeaders('application/json'),
    });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400,
      headers: corsHeaders('application/json'),
    });
  }

  const { symbol, name, price, change, klineSummary } = body;

  if (!symbol || !name) {
    return new Response(JSON.stringify({ error: 'Missing symbol/name' }), {
      status: 400,
      headers: corsHeaders('application/json'),
    });
  }

  const prompt = `Bạn là chuyên gia phân tích crypto. Hãy phân tích ngắn gọn ${name} (${symbol}) bằng tiếng Việt dựa trên dữ liệu sau:
- Giá hiện tại: $${Number(price).toFixed(2)}
- Thay đổi 24h: ${Number(change) >= 0 ? '+' : ''}${Number(change).toFixed(2)}%
- ${klineSummary || 'Không có dữ liệu kline'}

Yêu cầu: viết 3-4 câu ngắn gọn, bao gồm: (1) nhận định xu hướng ngắn hạn, (2) mức hỗ trợ/kháng cự gần nhất, (3) khuyến nghị ngắn hạn. Giọng văn chuyên nghiệp, dứt khoát. Thêm disclaimer cuối: "⚠ Đây không phải lời khuyên đầu tư."`;

  try {
    const groqRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${GROQ_KEY}`,
      },
      body: JSON.stringify({
        model:       'llama-3.3-70b-versatile',
        messages:    [{ role: 'user', content: prompt }],
        max_tokens:  400,
        temperature: 0.7,
      }),
    });

    if (!groqRes.ok) {
      const err = await groqRes.json();
      throw new Error(err.error?.message || `Groq HTTP ${groqRes.status}`);
    }

    const data = await groqRes.json();
    const text = data.choices?.[0]?.message?.content || 'Không có kết quả';

    return new Response(JSON.stringify({ result: text }), {
      status: 200,
      headers: corsHeaders('application/json'),
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: corsHeaders('application/json'),
    });
  }
}

function corsHeaders(contentType) {
  const h = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  if (contentType) h['Content-Type'] = contentType;
  return h;
}
