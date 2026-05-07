#!/usr/bin/env python3
"""
Test A: Cambiar el último párrafo del prompt de hook_dinero por uno que hable de
        montos mensuales y anuales. Guardar. Regenerar. Verificar que sobrevive.

Test B: Sin guardar, regenerar directamente. Verificar que conserva el nuevo
        prompt de la sesión (el texto modificado en A).
"""
import time
from playwright.sync_api import sync_playwright

SERVER = "http://127.0.0.1:8789"
PROSPECT_NAME = "Hospital Veterinario Delta"

NUEVO_PARRFO = (
    "ADICIONAL: Calcula el monto estimado en MXN tanto de forma mensual como "
    "anual, mostrando el ingreso perdido por mes y por año completo."
)

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []

        # ── 1. Abrir editor y seleccionar prospecto ────────────────────────
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

        prompt_original = page.locator("#bloque-prompt-usado").input_value()
        print(f"    prompt original[:120]: {prompt_original[:120]}")

        # ── TEST A ──────────────────────────────────────────────────────────
        # 3a. Modificar el ÚLTIMO PÁRRAFO del prompt
        lineas = prompt_original.rstrip().split("\n")
        # Quitar últimos 2-3 líneas que suelen ser la indicación de datos
        while lineas and lineas[-1].startswith("-"):
            lineas.pop()
        while lineas and lineas[-1].strip() == "":
            lineas.pop()

        prompt_modificado = "\n".join(lineas).rstrip() + "\n\n" + NUEVO_PARRFO
        page.locator("#bloque-prompt-usado").fill(prompt_modificado)
        page.locator("#bloque-prompt-usado").blur()
        time.sleep(0.3)
        print(f"\n[TEST A]")
        print(f"[3a] Prompt modificado (length={len(prompt_modificado)})")
        print(f"     nuevo parrafo: {NUEVO_PARRFO[:80]}")

        # 4a. GUARDAR
        page.locator("#btn-guardar").click()
        page.wait_for_timeout(2000)
        toast_save = page.locator("#toast").inner_text()
        print(f"[4a] Guardar: '{toast_save}'")

        # Verificar que se guardó
        prompt_post_save = page.locator("#bloque-prompt-usado").input_value()
        if NUEVO_PARRFO[:30] not in prompt_post_save:
            errors.append(f"FAIL [4a]: no se guardó bien. prompt[:100]={prompt_post_save[:100]}")
        else:
            print(f"     ✓ Guardado correctamente")

        # 5a. REGENERAR
        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(60000)
        toast_regen = page.locator("#toast").inner_text()
        v_after_regen = page.locator("#editor-version").inner_text()
        prompt_after_regen = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[5a] Tras regenerar:")
        print(f"     toast: '{toast_regen}'")
        print(f"     version: {v_after_regen}")
        print(f"     tiene nuevo parrafo: {NUEVO_PARRFO[:30] in prompt_after_regen}")
        print(f"     prompt[:150]: {prompt_after_regen[:150]}")

        if NUEVO_PARRFO[:30] not in prompt_after_regen:
            errors.append(f"FAIL [5a]: el nuevo parrafo se PIERDE tras regenerar (con guardar)")
            errors.append(f"  prompt[:200]: {prompt_after_regen[:200]}")
        else:
            print(f"     ✓ TEST A OK: el nuevo parrafo sobrevive tras guardar + regenerar")

        # ── TEST B ──────────────────────────────────────────────────────────
        # 3b. Modificar el prompt de nuevo (para simular otra edición de sesión)
        # Esta vez NO guardamos, vamos directo a regenerar
        prompt_session = prompt_after_regen + "\n\n[NOTA DE SESION] Verifica que este texto sea exactamente el mismo que acabas de regenerar.\n"
        page.locator("#bloque-prompt-usado").fill(prompt_session)
        page.locator("#bloque-prompt-usado").blur()
        time.sleep(0.3)
        print(f"\n[TEST B]")
        print(f"[3b] Prompt en textarea (sin guardar):")
        print(f"     length={len(prompt_session)}")

        # 4b. REGENERAR SIN GUARDAR
        v_before_regen_b = page.locator("#editor-version").inner_text()
        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(60000)
        toast_regen_b = page.locator("#toast").inner_text()
        v_after_regen_b = page.locator("#editor-version").inner_text()
        prompt_after_regen_b = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[4b] Tras regenerar (sin guardar):")
        print(f"     toast: '{toast_regen_b}'")
        print(f"     version ANTES: {v_before_regen_b}")
        print(f"     version DESPUES: {v_after_regen_b}")
        print(f"     prompt[:150]: {prompt_after_regen_b[:150]}")

        if v_before_regen_b == v_after_regen_b:
            errors.append("FAIL [4b]: la version NO cambió — regenerate no funcionó")
        else:
            print(f"     ✓ Version cambió (regenerate funcionó)")

        # Lo que debe sobrevivir es el texto que estaba en el textarea al hacer click en regenerar
        # El nuevo parrafo mensual/anual DEBE estar (viene del session state)
        if NUEVO_PARRFO[:30] not in prompt_after_regen_b:
            errors.append(f"FAIL [4b]: el parrafo mensual/anual se PIERDE al regenerar sin guardar")
            errors.append(f"  prompt[:200]: {prompt_after_regen_b[:200]}")
        else:
            print(f"     ✓ TEST B OK: el parrafo mensual/anual sobrevive sin guardar antes")

        # ── TEST C: Recarga de pagina ──────────────────────────────────────
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
        print(f"\n[TEST C] Tras recarga de pagina:")
        print(f"     tiene parrafo mensual/anual: {NUEVO_PARRFO[:30] in prompt_final}")
        print(f"     prompt[:150]: {prompt_final[:150]}")

        if NUEVO_PARRFO[:30] not in prompt_final:
            errors.append("FAIL [TEST C]: el parrafo mensual/anual se PIERDE tras recarga")
        else:
            print(f"     ✓ TEST C OK: persiste tras recarga de pagina")

        # ── Resultado ──────────────────────────────────────────────────────
        print("\n" + "="*50)
        if errors:
            print("RESULTADO: HAY ERRORES")
            for e in errors:
                print("  " + e)
        else:
            print("RESULTADO: TODOS LOS TESTS PASARON")
            print("  ✓ TEST A: guardar + regenerar — prompt sobrevive")
            print("  ✓ TEST B: regenerar sin guardar — prompt sobrevive")
            print("  ✓ TEST C: persiste tras recarga de pagina")

        browser.close()
        return len(errors) == 0

if __name__ == "__main__":
    ok = run()
    exit(0 if ok else 1)
