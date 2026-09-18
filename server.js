require('dotenv').config();
const express = require('express');
const cors = require('cors');

const app = express();
const PORT = Number(process.env.PORT || 3000);
const UPSTREAM_URL = process.env.TEXT_TO_VIDEO_API_URL;
const API_KEY = process.env.TEXT_TO_VIDEO_API_KEY;
const REQUEST_TIMEOUT_MS = Number(process.env.TEXT_TO_VIDEO_TIMEOUT_MS || 120000);

app.use(cors());
app.use(express.json({ limit: '20mb' }));

app.get('/api/health', (req, res) => {
  res.json({
    ok: true,
    message: 'PlayZone100 text-to-video API is running.',
    upstreamConfigured: Boolean(UPSTREAM_URL),
    hasApiKey: Boolean(API_KEY)
  });
});

app.post('/api/generate', async (req, res) => {
  try {
    const body = req.body || {};
    const prompt = typeof body.prompt === 'string' ? body.prompt.trim() : '';

    if (!prompt) {
      return res.status(400).json({
        error: 'Prompt is required.',
        message: 'Please provide a non-empty text prompt.'
      });
    }

    if (!UPSTREAM_URL) {
      return res.status(503).json({
        error: 'Upstream video API is not configured.',
        message: 'Set TEXT_TO_VIDEO_API_URL in your environment before using the generator.'
      });
    }

    const upstreamBody = {
      prompt,
      model: body.model || process.env.DEFAULT_MODEL_NAME || 'ltx-video',
      width: body.width || 768,
      height: body.height || 432,
      duration: body.duration || 4,
      ...body
    };

    delete upstreamBody.prompt;
    delete upstreamBody.model;

    const headers = {
      'Content-Type': 'application/json'
    };

    if (API_KEY) {
      headers.Authorization = `Bearer ${API_KEY}`;
    }

    const upstreamResponse = await fetch(UPSTREAM_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        prompt,
        model: body.model || process.env.DEFAULT_MODEL_NAME || 'ltx-video',
        width: body.width || 768,
        height: body.height || 432,
        duration: body.duration || 4,
        ...body
      }),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
    });

    const contentType = upstreamResponse.headers.get('content-type') || '';
    const responseText = await upstreamResponse.text();

    let parsed;
    try {
      parsed = responseText ? JSON.parse(responseText) : null;
    } catch (error) {
      parsed = null;
    }

    if (!upstreamResponse.ok) {
      return res.status(upstreamResponse.status || 500).json({
        error: 'Upstream generation failed.',
        status: upstreamResponse.status,
        detail: parsed || responseText || 'Unknown upstream error.'
      });
    }

    const videoUrl =
      parsed?.video_url ||
      parsed?.url ||
      parsed?.output_url ||
      parsed?.result?.video_url ||
      parsed?.data?.video_url ||
      parsed?.data?.[0]?.url ||
      parsed?.data?.[0]?.video_url ||
      parsed?.result?.output_url ||
      null;

    return res.json({
      ok: true,
      video_url: videoUrl,
      raw: parsed || {},
      prompt
    });
  } catch (error) {
    console.error('Text-to-video proxy error:', error);
    return res.status(500).json({
      error: 'Internal proxy error.',
      message: error.message || 'Unknown server error.'
    });
  }
});

app.use((req, res) => {
  res.status(404).json({ error: 'Not found.' });
});

app.listen(PORT, () => {
  console.log(`PlayZone100 text-to-video API running on http://localhost:${PORT}`);
});
