#!/usr/bin/env python3
"""
Flujo real del usuario:
1. Seleccionar fuentes de maps_audit + reviews
2. Modificar el prompt (quitar formato label/valor array)
3. Guardar
4. Regenerar
5. Verificar que el prompt siga siendo el personalizado
"""
import time
from playwright.sync_api import sync_playwright

SERVER = "http://127.0.0.1:8789"
PROSPECT_NAME = "Hospital Veterinario Delta"
PLACE_ID = "ChIJwyzO_QX_0YURXcI28Js0Dbg"

USER_PROMPT = (
    "Eres un experto en analisis financiero de negocios de salud en Mexico.\n"
    "Responde en texto plano, sin JSON, sin arrays de objetos label/valor.\n"
    "Solo parrafos claros en espanol mexicano.\n"
)

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []

        # ── 1. Editor y prospecto ──────────────────────────────────────────
        page.goto(f"{SERVER}/editor")
        page.wait_for_load_state("networkidle")
        inp = page.locator("#prospect-input")
        inp.click()
        inp.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(3)
        print("[1] Editor listo")

        # ── 2. Abrir bloque ───────────────────────────────────────────────
        page.wait_for_selector(".bloque-card", timeout=10000)
        first_card = page.locator(".bloque-card").first
        bloque_id = first_card.get_attribute("id").replace("bc-", "")
        first_card.click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)
        print(f"[2] Bloque abierto: {bloque_id}")

        # ── 3. Seleccionar fuentes (maps_audit + reviews) ─────────────────
        # maps_audit: Quick Wins, Score General
        # review_insights: Temas Positivos, Temas Negativos

        def expand_and_toggle(sec, sub):
            """Abre la sección del árbol y marca la subsección."""
            header = page.locator(f".tree-section-header[data-sec=\"{sec}\"]")
            if header.count() > 0:
                # Si está cerrado, abrirlo
                parent = header.first.locator("..")
                cls = parent.get_attribute("class") or ""
                if "expanded" not in cls:
                    header.first.click()
                    time.sleep(0.4)
            # Ahora buscar el label visible de esa subsección
            selector = f".fuente-check.sub[data-sec=\"{sec}\"][data-sub=\"{sub}\"]"
            label = page.locator(selector)
            if label.count() == 0:
                print(f"    [WARN] no se encontro fuente: {sec}/{sub}")
                return
            if label.first.is_visible():
                label.first.click()
                time.sleep(0.2)

        # Seleccionar Quick Wins de maps_audit
        expand_and_toggle("maps_audit", "Quick Wins")
        # Seleccionar Score General de maps_audit
        expand_and_toggle("maps_audit", "Score General")
        # Seleccionar Temas Positivos de review_insights
        expand_and_toggle("review_insights", "Temas Positivos")
        # Seleccionar Temas Negativos de review_insights
        expand_and_toggle("review_insights", "Temas Negativos")

        checked_count = page.locator(".fuente-check.checked").count()
        print(f"[3] Fuentes seleccionadas (checked): {checked_count}")

        # ── 4. Modificar el prompt ────────────────────────────────────────
        page.locator("#bloque-prompt-usado").fill(USER_PROMPT)
        page.locator("#bloque-prompt-usado").blur()
        time.sleep(0.3)
        print(f"[4] Prompt modificado (length={len(USER_PROMPT)})")

        # ── 5. Guardar ────────────────────────────────────────────────────
        page.locator("#btn-guardar").click()
        page.wait_for_timeout(2000)
        toast_save = page.locator("#toast").inner_text()
        print(f"[5] Guardar: '{toast_save}'")

        # Verificar que se guardó
        prompt_post_save = page.locator("#bloque-prompt-usado").input_value()
        if "sin JSON" not in prompt_post_save:
            errors.append(f"FAIL [5]: prompt no se guardo bien. prompt[:100]={prompt_post_save[:100]}")
        else:
            print(f"    ✓ Prompt guardado correctamente")

        # ── 6. Regenerar (tarda ~30-50s) ──────────────────────────────────
        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(60000)  # esperar suficiente para regenerate
        toast_regen = page.locator("#toast").inner_text()
        version_after = page.locator("#editor-version").inner_text()
        prompt_after = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[6] Tras regenerar:")
        print(f"    toast: '{toast_regen}'")
        print(f"    version: {version_after}")
        print(f"    has 'sin JSON': {'sin JSON' in prompt_after}")
        print(f"    has 'datos_concretos': {'datos_concretos' in prompt_after}")
        print(f"    prompt[:150]: {prompt_after[:150]}")

        if "sin JSON" not in prompt_after:
            errors.append(f"FAIL [6]: texto personalizado se perdio tras regenerar")
            errors.append(f"  prompt[:200]: {prompt_after[:200]}")
        else:
            print(f"    ✓ Texto personalizado sobrevive")

        if "datos_concretos" in prompt_after:
            errors.append("FAIL [6]: se reinsertó el formato 'datos_concretos' original")
        else:
            print("    ✓ Formato original NO reaparece")

        # ── 7. Recargar y verificar ────────────────────────────────────────
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        inp2 = page.locator("#prospect-input")
        inp2.click()
        inp2.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(2)

        page.wait_for_selector(".bloque-card", timeout=10000)
        page.locator(f"#bc-{bloque_id}").click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)

        prompt_final = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[7] Tras recarga:")
        print(f"    has 'sin JSON': {'sin JSON' in prompt_final}")
        print(f"    prompt[:150]: {prompt_final[:150]}")

        if "sin JSON" not in prompt_final:
            errors.append("FAIL [7]: prompt se perdio tras recarga de pagina")
        else:
            print("    ✓ Texto persiste tras recarga")

        # ── Resultado ──────────────────────────────────────────────────────
        print("\n" + "="*50)
        if errors:
            print("RESULTADO: BUG ENCONTRADO")
            for e in errors:
                print("  " + e)
        else:
            print("RESULTADO: TODO OK — no hay bug en el flujo real del usuario")

        browser.close()
        return len(errors) == 0

if __name__ == "__main__":
    ok = run()
    exit(0 if ok else 1)
