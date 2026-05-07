#!/usr/bin/env python3
"""
Test completo del bug: prompt personalizado sobrevive a regenerar + recarga de pagina.

Escenario real del usuario:
  1. Abre bloque → ve prompt original
  2. Modifica prompt manualmente
  3. (Opcional) guarda
  4. Click "Regenerar"
  5. PROBLEMA: el prompt vuelve al original

Este test verifica:
  A) Tras regenerar, el bloque devuelto tiene el prompt personalizado
  B) Tras RECARGAR la pagina y reabrir el bloque, el prompt es el personalizado
"""

import time
from playwright.sync_api import sync_playwright

SERVER = "http://127.0.0.1:8789"
PROSPECT_NAME = "Hospital Veterinario Delta"
PLACE_ID = "ChIJwyzO_QX_0YURXcI28Js0Dbg"
MARKER = "BROWSER_TEST_MARKER_ZXY_987"

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []

        # ── 1. Cargar editor y seleccionar prospecto ────────────────────────
        page.goto(f"{SERVER}/editor")
        page.wait_for_load_state("networkidle")

        inp = page.locator("#prospect-input")
        inp.click()
        inp.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(3)   # esperar autogen + carga completa
        print("[1] Editor listo")

        # ── 2. Leer prompt original ─────────────────────────────────────────
        page.wait_for_selector(".bloque-card", timeout=10000)
        first_card = page.locator(".bloque-card").first
        bloque_id = first_card.get_attribute("id").replace("bc-", "")
        first_card.click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)

        prompt_orig = page.locator("#bloque-prompt-usado").input_value()
        version_orig = page.locator("#editor-version").inner_text()
        print(f"[2] Bloque abierto: {bloque_id}")
        print(f"    prompt_original[:80]: {prompt_orig[:80]}")
        print(f"    version: {version_orig}")

        # ── 3. Modificar el prompt con el marker ────────────────────────────
        prompt_modificado = (
            prompt_orig.strip() + "\n\n"
            f"-- [{MARKER}] TEST MARKER --\n"
            "HABLA EN FORMA INFORMAL. Responde maximo 3 oraciones.\n"
        )
        page.locator("#bloque-prompt-usado").fill(prompt_modificado)
        page.locator("#bloque-prompt-usado").blur()
        time.sleep(0.5)
        print(f"[3] Prompt modificado (length={len(prompt_modificado)})")

        # ── 4. Guardar ───────────────────────────────────────────────────────
        page.locator("#btn-guardar").click()
        page.wait_for_timeout(2000)
        toast = page.locator("#toast").inner_text()
        print(f"[4] Guardar toast: '{toast}'")

        # ── 5. Recargar la pagina (simula cerrar/reabrir navegador) ──────────
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        print("[5] Pagina recargada")

        # ── 6. Reseleccionar prospecto (necesario tras reload) ──────────────
        inp = page.locator("#prospect-input")
        inp.click()
        inp.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(2)
        print("[6] Prospecto reseleccionado")

        # ── 7. Abrir el MISMO bloque ─────────────────────────────────────────
        page.wait_for_selector(".bloque-card", timeout=10000)
        page.locator(f"#bc-{bloque_id}").click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)

        prompt_post_reload = page.locator("#bloque-prompt-usado").input_value()
        version_post_reload = page.locator("#editor-version").inner_text()
        print(f"[7] Bloque re-abierto tras reload")
        print(f"    prompt_post_reload[:80]: {prompt_post_reload[:80]}")
        print(f"    version: {version_post_reload}")
        print(f"    has MARKER: {MARKER in prompt_post_reload}")

        if not (MARKER in prompt_post_reload):
            errors.append(f"FAIL [7]: marker NO presente tras reload. prompt[:100]={prompt_post_reload[:100]}")
        else:
            print("    ✓ Marker presente tras reload")

        # ── 8. REGENERAR ───────────────────────────────────────────────────
        prompt_for_regen = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[8] Prompt enviado a regenerate (length={len(prompt_for_regen)}):")
        print(f"    has MARKER: {MARKER in prompt_for_regen}")

        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(10000)

        toast_regen = page.locator("#toast").inner_text()
        version_after = page.locator("#editor-version").inner_text()
        prompt_after_regen = page.locator("#bloque-prompt-usado").input_value()
        print(f"[8b] Tras regenerar:")
        print(f"    toast: '{toast_regen}'")
        print(f"    version: {version_after}")
        print(f"    has MARKER: {MARKER in prompt_after_regen}")
        print(f"    prompt[:80]: {prompt_after_regen[:80]}")

        if not (MARKER in prompt_after_regen):
            errors.append(f"FAIL [8]: marker NO presente tras regenerar. prompt[:100]={prompt_after_regen[:100]}")
        else:
            print("    ✓ Marker presente tras regenerar")

        # ── 9. Recargar de nuevo y verificar ────────────────────────────────
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        inp = page.locator("#prospect-input")
        inp.click()
        inp.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(2)

        page.wait_for_selector(".bloque-card", timeout=10000)
        page.locator(f"#bc-{bloque_id}").click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)

        prompt_final = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[9] Prompt tras 2da recarga:")
        print(f"    has MARKER: {MARKER in prompt_final}")
        print(f"    prompt[:100]: {prompt_final[:100]}")

        if not (MARKER in prompt_final):
            errors.append(f"FAIL [9]: marker NO presente tras 2da recarga. prompt[:100]={prompt_final[:100]}")
        else:
            print("    ✓ Marker presente tras 2da recarga")

        # ── Resultado ──────────────────────────────────────────────────────
        print("\n" + "="*50)
        if errors:
            print("RESULTADO: HAY ERRORES")
            for e in errors:
                print("  " + e)
        else:
            print("RESULTADO: TODO PASÓ")
            print("  ✓ Prompt sobrevive a guardar + recarga")
            print("  ✓ Prompt sobrevive a regenerar")
            print("  ✓ Prompt sobrevive a recarga post-regeneracion")

        browser.close()
        return len(errors) == 0

if __name__ == "__main__":
    ok = run()
    exit(0 if ok else 1)
