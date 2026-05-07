# CLAUDE.md

Este archivo proporciona orientación a Claude Code para trabajar en este repositorio.

## Memoria

- Lee `docs/PLAN.md` al iniciar.
- Actualiza `docs/PLAN.md` al concluir cualquier subtarea o `/brainstorming`.

## GitHub

- **Token:** guardado en macOS Keychain via `gh auth login`
- **Credential helper:** `gh auth git-credential` configurado globalmente
- Para nuevos repos: `git remote add origin git@github.com:oxcarod/salesCrafter.git`
- No poner tokens en URLs remotas — usar `gh` como credential helper

## Concepto

salesCrafter genera contenido comercial editable a partir de la UnifiedCache de salesSystem.

- **salesSystem** (puerto 8788) = investigar y auditar
- **salesCrafter** (puerto 8789) = sintetizar investigación en pitches editables

## Regla: Solo lectura de UnifiedCache

salesCrafter SOLO LEE de la UnifiedCache. Nunca escribe en ella.
