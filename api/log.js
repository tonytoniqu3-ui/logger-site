const { createClient } = require('@supabase/supabase-js');

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, error: 'Use POST' });
  }

  const SUPABASE_URL = process.env.SUPABASE_URL;
  const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
    return res.status(500).json({ ok:false, error:'Missing env vars' });
  }

  const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const { event_type, user_name, email, payload } = req.body || {};
  const ua = req.headers['user-agent'] || null;
  const ip = req.headers['x-forwarded-for']?.split(',')[0]?.trim() || req.socket?.remoteAddress || null;

  const { error } = await sb.from('site_logs').insert([{
    event_type: event_type || 'unknown',
    user_name: user_name || null,
    email: email || null,
    payload: payload || {},
    ip, ua
  }]);

  if (error) return res.status(500).json({ ok:false, error: String(error.message || error) });
  return res.json({ ok:true });
};
