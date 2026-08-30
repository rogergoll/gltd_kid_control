# API — GLTD Kid Control Server

Base: `http://<server>:8123`

## GET /api/health
```json
{ "status": "ok", "version": "0.1.0" }
```

## GET /api/profiles
Lista todos os perfis. Retorna array de `Profile.to_dict()`.

## GET /api/profiles/{id}
Perfil específico ou `404`. Cada perfil inclui os campos de limite de tempo:
`daily_limit_minutes` e `youtube_limit_minutes` (0 = sem limite).

## GET /api/profiles/{id}/blocks
Bloqueios aplicáveis ao perfil, separados por tipo, cada item com o `file` de origem:
```json
{
  "channels": [{ "handle": "@x", "nome_canal": "...", "url": "...", "categoria": "...", "file": "block_child1.csv" }],
  "videos":  [{ "url": "https://...", "nome_canal": "...", "file": "block_manual_child1.csv" }],
  "urls":    [{ "url": "...", "categoria": "dominio", "file": "..." }]
}
```

## POST /api/profiles/{id}/unblock
Remove uma entrada de uma lista de bloqueio. Body:
```json
{ "file": "block_manual_child1.csv", "handle": "@x" }
```
ou `{ "file": "...", "url": "https://..." }`. Resposta: `{ "ok": true, "filename": "..." }`.

## POST /api/profiles/{id}/block-{channel|video|url|domain}
Adiciona um bloqueio manual ao perfil (grava em `block_manual_<id>.csv`).
Body (channel): `{ "handle": "@x" }`; (video/url/domain): `{ "url": "..." }`.

## GET /api/lists
Resumo das listas carregadas (quantidade de canais por arquivo):
```json
{ "block": { "block_child1.csv": 22 }, "allow": { "allow_child1.csv": 34 } }
```

## GET /api/lists/file/{filename}
Conteúdo bruto de uma lista:
```json
{ "filename": "block_child1.csv", "kind": "block", "count": 22, "content": "handle,nome_canal,...\n" }
```

## PUT /api/lists/file/{filename}
Salva o conteúdo CSV de uma lista (valida o cabeçalho antes). Body: `{ "content": "..." }`.
Resposta: `{ "ok": true, "filename": "...", "kind": "...", "count": n }`.

## GET /api/history?profile={id}&limit={n}
Histórico de visualizações (mais recentes primeiro). Cada item:
```json
{
  "id": 1, "profile_id": "child1", "channel_handle": "@ManualDoMundo",
  "channel_name": "Manual do Mundo", "video_title": "...", "video_url": "...",
  "thumb_url": "...", "description": "...", "watched_at": "2026-08-13T17:00:00"
}
```

## POST /api/history
Client reporta um vídeo assistido. Body:
```json
{
  "profile_id": "child1", "channel_handle": "@ManualDoMundo",
  "channel_name": "Manual do Mundo", "video_title": "...", "video_url": "...",
  "thumb_url": "...", "description": "...", "watched_at": "2026-08-13T17:00:00"
}
```
Resposta: `{ "id": <id> }` com status `201`.

## POST /api/filters
Adiciona expressão/frase de bloqueio a um perfil. Body:
```json
{ "profile_id": "child1", "expression": "namoro" }
```
Resposta: `{ "ok": true, "filters": [...] }` ou `{ "ok": false, "error": "..." }`.
