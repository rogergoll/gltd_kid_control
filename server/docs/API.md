# API — GLTD Kid Control Server

Base: `http://<server>:8123`

## GET /api/health
```json
{ "status": "ok", "version": "0.1.0" }
```

## GET /api/profiles
Lista todos os perfis. Retorna array de `Profile.to_dict()`.

## GET /api/profiles/{id}
Perfil específico ou `404`.

## GET /api/lists
Resumo das listas carregadas (quantidade de canais por arquivo):
```json
{ "block": { "block_child1.csv": 22 }, "allow": { "allow_child1.csv": 34 } }
```

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

> Endpoints de escrita de canais (adicionar/remover das listas) e autenticação
> serão adicionados em iterações futuras.
