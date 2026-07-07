# Picklight promo video

~43-second music-driven promo for **Picklight** — semantic file search powered by [Moss](https://moss.dev).

## Story

1. Hero — universal file-search problem
2. Spotlight failure — filename search returns the wrong file
3. **Moss platform** — zoom rail (real-time semantic search, sub-10ms retrieval)
4. Product reveal — Picklight demo (⌘⇧M, semantic query → correct PDF)
5. **Why Moss** — hybrid retrieval, runtime not vector DB, local-first, production SDKs
6. **Outro** — “your favorite product” → Capvolt + Picklight → Powered by Moss

## Commands

```bash
npm install
npm run dev
npm run render   # → out/picklight-promo.mp4
```

Optional — regenerate SFX/music via ElevenLabs (requires `ELEVENLABS_API_KEY` in `promo/.env` or `examples/moss-pikachu/.env`):

```bash
npm run generate-audio
```

## Specs

- 1920×1080, 30fps, ~43 seconds
- No voiceover

## Instagram vertical export

Pre-rendered 9:16 cut: [`picklight-instagram-vertical.mp4`](picklight-instagram-vertical.mp4) (demo on top, screen-recording voiceover on bottom).

Rebuild after re-rendering the promo:

```bash
# Place voiceover MOV in examples/moss-pikachu/ (or set VOICEOVER_MOV)
../scripts/combine-instagram-vertical.sh
```

Requires [Homebrew ffmpeg](https://formulae.brew.sh/formula/ffmpeg) (`brew install ffmpeg`). Demo music is mixed at 15% under the voiceover (`MUSIC_VOLUME=0.15`).
