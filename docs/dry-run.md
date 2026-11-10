# Family dry-run kit (OPS-05)

## Purpose

Before the 1 Dec 2026 freeze, 2-3 relatives each use their own phone to sign in, join the
family event, add a wish and claim someone else's (test) wish. Whatever confuses them is fixed
in one follow-up quick task. Aim: done by about 22 Nov 2026. The repo provides the materials
below; running the dry-run and recording it is human work.

## Before sending (author)

1. Deploy this phase and watch the deploy run, including the health check step (it must print
   `healthy`). Then run `bash scripts/smoke.sh https://gifter.remesh.cz`; checks (b), (o) and
   (p) must pass.
2. Make sure backups run (DEPLOYMENT.md, "Backups and restore") and that `/privacy/` now shows
   the nightly-backup sentences (they appear once the first nightly backup has written its
   marker).
3. Use the real family event, so the relatives can stay in it afterwards. Add one wish named
   `Zkušební přání – nekupovat` (test wish) for the claim step. Test claims go only on this
   wish, never on a real Christmas wish.
4. Do the real-device checks below.

## Message for the family chat (Czech, ready to paste)

> Ahoj, připravil jsem aplikaci Gifter: každý si tam založí seznam přání a ostatní z rodiny
> uvidí, co si přeješ, a domluví se, kdo co koupí. Ty, komu přání patří, nikdy nevidíš, kdo
> ho zamluvil.
>
> Odkaz na pozvánku: **[SEM VLOŽIT ODKAZ NA POZVÁNKU]**
>
> Otevři ho v Chrome nebo v Safari. Pokud se odkaz otevře uvnitř Messengeru nebo Instagramu,
> klepni na nabídku ⋯ v rohu obrazovky a vyber Otevřít v prohlížeči (Google v těchto aplikacích
> přihlášení nepovolí).
>
> Zkus prosím těchto pět kroků:
>
> 1. Přihlas se tlačítkem „Přihlásit se přes Google".
> 2. Připoj se k akci tlačítkem „Připojit se".
> 3. Přidej si jedno přání tlačítkem „Přidat přání".
> 4. U cizího přání „Zkušební přání – nekupovat" stiskni „Pořídím to" a hned potom „Uvolnit".
> 5. Napiš sem do chatu, co ti nebylo jasné nebo co nešlo.
>
> Prosím piš, co bylo zmatené, slovy. Neposílej sem snímky obrazovky stránky akce ani stránky
> „Moje zamluvení", protože na nich je vidět, kdo co kupuje.

## Checklist for each relative (Czech)

1. Přihlas se přes Google: „Přihlásit se přes Google".
2. Připoj se k akci: „Připojit se".
3. Přidej přání: „Přidat přání".
4. U zkušebního přání „Zkušební přání – nekupovat" stiskni „Pořídím to" a potom „Uvolnit".
5. Napiš do rodinného chatu, co bylo zmatené (slovy, bez snímků obrazovky).

Author note: the checklist and message ask for problems in words. Never invite screenshots of
event pages or My claims (Moje zamluvení) into the family chat: you are a giftee and read it,
and those pages show who is buying what.

## Real-device checks (author)

These confirm the phone pass of plan 04-04 on real hardware, in Czech:

- iPhone Safari and Android Chrome at about 360 px wide: no horizontal scrolling on the
  landing page, My events, an event, My wishlist and My claims.
- Buttons are easy to tap (about 44 px) and stack full width on a narrow screen.
- Long wish names, notes and links wrap instead of running off the screen.
- The EN / CS switch is reachable and works, and the choice stays after reloading.
- Messenger and Instagram in-app browsers (open the invite link from a chat there): the page
  shows the "Open Gifter in your browser" hint with Copy link and Continue anyway. Write down
  the real wording of the browser menu item (it may differ from "Open in browser") for a
  later copy fix.

## After the dry-run (author)

- Collect the feedback from the family chat and paste it to Claude for a follow-up quick task
  before 1 Dec.
- Ask the Czech-speaking relative which Czech wording sounded wrong, and fix it in
  `locale/cs/LC_MESSAGES/django.po`.
- Delete the test wish `Zkušební přání – nekupovat` (and make sure no test claim remains).

## Launch order

1. Push `main` and watch the deploy, including the new health check.
2. Live smoke: `bash scripts/smoke.sh https://gifter.remesh.cz`.
3. Install the backup timer and run the first backup.
4. Check that `/privacy/` now shows the nightly-backup sentences.
5. Restore drill; record it.
6. Real-device checks (above).
7. Send the message to the family chat.
8. Dry-run by about 22 Nov.
9. Fixes from the feedback (one quick task).
10. Freeze on 1 Dec.

## Dry-run record

| Date | Relative (initials) | Phone and browser | Steps 1-5 done | Problems reported |
|------|---------------------|-------------------|----------------|-------------------|
| not yet run | | | | |
