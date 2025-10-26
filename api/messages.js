const { createClient } = require('@supabase/supabase-js');

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    return res.status(204).end();
  }
  if (req.method !== 'GET') {
    return res.status(405).json({ ok:false, error: 'Method not allowed' });
  }

  try {
    const SUPABASE_URL = process.env.SUPABASE_URL;
    const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
    if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
      return res.status(500).json({ ok:false, error:'Env vars missing (SUPABASE_URL / SUPABASE_SERVICE_KEY)' });
    }

    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

    const limit = Math.min(parseInt(req.query.limit || '100', 10), 200);

    const { data, error } = await sb
      .from('site_logs')
      .select('created_at, user_name, payload', { head: false })
      .eq('event_type', 'message_sent')
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      console.error('Supabase select error:', error);
      return res.status(500).json({
        ok: false,
        error: error.message || 'Supabase error',
        details: error
      });
    }

    const items = (data || []).map(row => ({
      at: row.created_at,
      user: row.user_name || 'anonyme',
      message: row?.payload?.message ? String(row.payload.message) : ''
    }));

    return res.json({ ok:true, items });
  } catch (e) {
    console.error('Handler error:', e);
    return res.status(500).json({
      ok:false,
      error: e?.message || String(e)
    });
  }
};
