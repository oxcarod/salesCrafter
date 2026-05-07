#!/usr/bin/env python3
"""
Playwright test: verifica que el prompt personalizado sobrevive a la regeneración.
Pasos:
1. Abre /editor, selecciona prospecto, abre bloque
2. Modifica el prompt, guarda
3. Regenera
4. Verifica que el prompt de vuelta sea el que el usuario editó (no el original)
"""

import re, time, json
from playwright.sync_api import sync_playwright

SERVER = "http://127.0.0.1:8789"
PROSPECT_NAME = "Hospital Veterinario Delta"
PLACE_ID = "ChIJwyzO_QX_0YURXcI28Js0Dbg"

UNIQUE_MARKER = "XYZ_UNIQUE_MARKER_12345_XYZ"

def run():
    errors = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        # ── 1. Abrir editor ───────────────────────────────────────────────
        page.goto(f"{SERVER}/editor")
        page.wait_for_load_state("networkidle")
        print("[1] Editor cargado OK")

        # ── 2. Seleccionar prospecto ─────────────────────────────────────
        input_box = page.locator("#prospect-input")
        input_box.click()
        input_box.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(2)  # esperar autogen
        print("[2] Prospecto seleccionado OK")

        # ── 3. Seleccionar bloque (primero disponible) ─────────────────────
        page.wait_for_selector(".bloque-card", timeout=10000)
        first_card = page.locator(".bloque-card").first
        bloque_id = first_card.get_attribute("id").replace("bc-", "")
        first_card.click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        print(f"[3] Bloque abierto: {bloque_id}")

        # ── 4. Leer versión y prompt original ─────────────────────────────
        version_before = page.locator("#editor-version").inner_text()
        prompt_textarea = page.locator("#bloque-prompt-usado")
        prompt_original = prompt_textarea.input_value()
        print(f"    version_before: {version_before}")
        print(f"    prompt_original (first 80): {prompt_original[:80]}")

        # ── 5. Modificar el prompt con nuestro marker ──────────────────────
        prompt_modificado = (
            prompt_original.strip() + "\n\n"
            f"[MODIFICADO POR TEST — {UNIQUE_MARKER}]\n"
            "Ahora habla en tono informal y da solo 2 recomendaciones concretas.\n"
        )
        prompt_textarea.fill(prompt_modificado)
        prompt_textarea.blur()
        time.sleep(0.5)
        print("[5] Prompt modificado con marker")

        # ── 6. Guardar ──────────────────────────────────────────────────────
        page.locator("#btn-guardar").click()
        page.wait_for_timeout(1500)
        toast_text = page.locator("#toast").inner_text()
        print(f"[6] Guardar toast: {toast_text}")

        # Re-abrir para confirmar que guardó bien
        page.locator(f"#bc-{bloque_id}").click()
        page.wait_for_selector("#bloque-editor.visible", timeout=4000)
        time.sleep(0.5)
        prompt_after_save = page.locator("#bloque-prompt-usado").input_value()
        if UNIQUE_MARKER not in prompt_after_save:
            errors.append(f"FAIL [6]: marker NO apareció tras guardar. prompt[:80]={prompt_after_save[:80]}")
        else:
            print(f"[6b] Confirmado: marker presente tras guardar")
        print(f"    prompt_after_save (first 80): {prompt_after_save[:80]}")

        # ── 7. Regenerar ──────────────────────────────────────────────────
        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(8000)  # esperar respuesta de Claude
        toast_regen = page.locator("#toast").inner_text()
        print(f"[7] Regenerar toast: {toast_regen}")

        # ── 8. Verificar versión cambió ──────────────────────────────────
        version_after = page.locator("#editor-version").inner_text()
        print(f"    version_after: {version_after}")

        # ── 9. Leer prompt tras regeneración ─────────────────────────────
        time.sleep(1)
        prompt_after_regen = page.locator("#bloque-prompt-usado").input_value()
        print(f"    prompt_after_regen (first 120): {prompt_after_regen[:120]}")

        # ── 10. ASSERT ────────────────────────────────────────────────────
        print("\n── RESULTADO ──")
        if errors:
            for e in errors:
                print(e)
        else:
            if UNIQUE_MARKER in prompt_after_regen:
                print("PASS: el prompt modificado sobrevivió a la regeneración")
                print(f"      marker presente en prompt_post_regen[:120]: {prompt_after_regen[:120]}")
            else:
                print("FAIL: el prompt fue REVERTIDO al original tras regeneración")
                print(f"      expected marker {UNIQUE_MARKER}")
                print(f"      got prompt[:120]: {prompt_after_regen[:120]}")
                errors.append("prompt reverted to original")

        # Guardar logs del browser para diagnóstico
        browser_logs = []
        page.on("console", lambda m: browser_logs.append(m.text))
        print(f"\n[DEBUG] Console logs: {browser_logs[-10:]}")

        browser.close()

    if errors:
        print("\nHUBO ERRORES — ver arriba")
        exit(1)
    else:
        print("\nTEST PASÓ")
        exit(0)

if __name__ == "__main__":
    run()
