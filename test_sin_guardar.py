#!/usr/bin/env python3
"""
Escenario exacto del bug del usuario:
1. Abre bloque
2. Modifica el prompt (sin guardar antes)
3. Click "Regenerar" INMEDIATAMENTE (sin guardar)
4. Verificar que el prompt siga siendo el personalizado
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

        page.goto(f"{SERVER}/editor")
        page.wait_for_load_state("networkidle")
        inp = page.locator("#prospect-input")
        inp.click()
        inp.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(3)
        print("[1] Editor listo")

        page.wait_for_selector(".bloque-card", timeout=10000)
        first_card = page.locator(".bloque-card").first
        bloque_id = first_card.get_attribute("id").replace("bc-", "")
        first_card.click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)
        print(f"[2] Bloque abierto: {bloque_id}")
        v_orig = page.locator("#editor-version").inner_text()
        print(f"    version inicial: {v_orig}")

        # Modificar prompt SIN guardar primero
        page.locator("#bloque-prompt-usado").fill(USER_PROMPT)
        page.locator("#bloque-prompt-usado").blur()
        time.sleep(0.3)

        prompt_in_textarea = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[3] Prompt en textarea (SIN guardar):")
        print(f"    length={len(prompt_in_textarea)}, has_marker={'sin JSON' in prompt_in_textarea}")
        print(f"    prompt[:100]: {prompt_in_textarea[:100]}")

        # Regenerar INMEDIATAMENTE — sin hacer click en Guardar
        print(f"\n[4] Click en Regenerar (sin guardar primero)...")
        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(60000)  # esperar a que termine regenerate

        toast_regen = page.locator("#toast").inner_text()
        v_after = page.locator("#editor-version").inner_text()
        prompt_after = page.locator("#bloque-prompt-usado").input_value()

        print(f"\n[5] Tras regenerar (sin guardar):")
        print(f"    toast: '{toast_regen}'")
        print(f"    version: {v_after} (antes: {v_orig})")
        print(f"    has 'sin JSON': {'sin JSON' in prompt_after}")
        print(f"    has 'datos_concretos': {'datos_concretos' in prompt_after}")
        print(f"    prompt[:150]: {prompt_after[:150]}")

        # Assertions
        if "sin JSON" not in prompt_after:
            errors.append(f"FAIL: texto personalizado se PIERDE al regenerar sin guardar")
            errors.append(f"  prompt[:200]: {prompt_after[:200]}")
        else:
            print("    ✓ Texto personalizado sobrevive (sin guardar antes)")

        if "datos_concretos" in prompt_after:
            errors.append("FAIL: se reinsertó el formato 'datos_concretos' del template original")
        else:
            print("    ✓ Formato original NO reaparece")

        if v_orig != v_after:
            print(f"    ✓ Version cambio: {v_orig} -> {v_after}")
        else:
            errors.append(f"FAIL: version NO cambio (regenerate no funciono): {v_orig} == {v_after}")

        # Recargar y verificar que persiste en storage
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
        print(f"\n[6] Tras recarga de pagina:")
        print(f"    has 'sin JSON': {'sin JSON' in prompt_final}")
        print(f"    prompt[:150]: {prompt_final[:150]}")

        if "sin JSON" not in prompt_final:
            errors.append("FAIL: prompt se PIERDE tras recarga de pagina")
        else:
            print("    ✓ Texto persiste tras recarga")

        # ── Resultado ──────────────────────────────────────────────────────
        print("\n" + "="*50)
        if errors:
            print("RESULTADO: BUG ENCONTRADO")
            for e in errors:
                print("  " + e)
        else:
            print("RESULTADO: TODO OK — el prompt sobrevive incluso sin guardar antes")

        browser.close()
        return len(errors) == 0

if __name__ == "__main__":
    ok = run()
    exit(0 if ok else 1)
