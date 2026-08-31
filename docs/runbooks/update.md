========================================================================
  LAND ALLOCATION SYSTEM — UPDATE TO ${APP_VERSION} (build ${APP_BUILD})
  For the office computer that ALREADY runs the app
========================================================================

If the app has NEVER been on this computer, close this and open
INSTALL.txt instead.

Nothing gets installed today. Docker and WSL are already on this
machine and stay exactly as they are. You can ignore the "installers"
folder on this drive completely.

Nothing of yours is replaced: your cases, your scanned documents, your
logins, your categories and your settings all stay. About 15 minutes.


------------------------------------------------------------------------
  READ THIS ONCE BEFORE YOU START
------------------------------------------------------------------------

  ** DO NOT open this new folder and start the app from inside it, and
     do not rename or move the folder you already use. **

  Docker names the app — and its database — after the folder it is
  started from, unless COMPOSE_PROJECT_NAME is set in your .env (see
  STEP M1). Start it from a folder with a different name and the app
  comes up EMPTY: every case gone from the screen. Nothing is deleted,
  the app is simply looking at the wrong database, but it is
  frightening and it is avoidable.

  So the whole update is: you copy FOUR THINGS from this drive INTO
  the folder the office already uses, and you run everything there.


------------------------------------------------------------------------
  THE SIX STEPS
------------------------------------------------------------------------

STEP 1.  Open PowerShell inside your CURRENT install folder — the one
         you have always used, the one with your .env file in it.
         (Open it in File Explorer, hold SHIFT, right-click empty
          space, choose "Open PowerShell window here". On Windows 11
          that item may read "Open in Terminal" — same thing. If
          neither is there, click the address bar, type powershell
          and press Enter.)

STEP 2.  BACK UP FIRST. It is the only way back. Type:

             docker compose exec backend python manage.py backup_db

         Then plug in the external drive and copy BOTH of these folders
         onto it:
             Desktop\LandAllocationData\db-backups
             Desktop\LandAllocationData\documents

         The database alone is not a complete backup — the dump holds
         the cases, the documents folder holds the scans. Together they
         are the whole system; either one on its own restores badly.
         For this update the db-backups folder is the one that matters,
         since nothing below touches documents — but copy both while
         the drive is in your hand.

         (If you have already done the MOVING section at the end of this
          sheet, those folders are now under
              C:\ProgramData\LandAllocation\LandAllocationData)

         ** Do not skip this. Everything below is safe, but a backup is
            what makes that true. **

STEP 3.  Write down what Docker calls the app, so you can prove at the
         end that nothing moved. Type:

             docker compose ls

         Copy the word under NAME onto your paper. It must read the
         SAME in step 6.

STEP 4.  Stop the app. This deletes nothing. Type:

             docker compose down

STEP 5.  From this drive, copy these FOUR onto the ones with the same
         name in your CURRENT install folder, replacing them:

             images.tar.gz
             docker-compose.yml
             VERSION
             nginx              (the whole folder)

         ** Do NOT copy .env.example, and do NOT touch your .env file.
            It holds your database password. If you replace it, the
            app cannot open its own database. **

STEP 6.  Back in PowerShell, still in your CURRENT folder, type these
         three, one at a time, waiting for each:

             docker load -i images.tar.gz
             docker compose up -d
             docker compose exec backend python manage.py migrate

         The middle one needs about a minute before the app answers.


------------------------------------------------------------------------
  NOW CHECK IT, IN THIS ORDER
------------------------------------------------------------------------

  1. Type:  docker compose ls
     The NAME must be the same word you wrote down in step 3.

  2. Open  http://localhost/
     The footer must read:  ${APP_VERSION} (build ${APP_BUILD})

  3. Log in and open the case list. YOUR CASES MUST ALL BE THERE.

  4. Open one existing case and check its documents still open.

  ** If the case list is empty: STOP. Do not create anything, do not
     type anything in. Nothing is lost — the app is pointed at the
     wrong database and it can be pointed back. Call the developer. **

  You do NOT need to run create_admin or install_templates again.
  Doing so is not needed and only invites mistakes.


------------------------------------------------------------------------
  ONE-TIME: MOVING THE APP AND ITS DATA OFF THE DESKTOP
------------------------------------------------------------------------

  Do this ONLY after the update above is finished and every check on it
  has passed. It is a separate job — set aside about half an hour, and
  do not start it late in the day. It is done once and never again.

  ** If a previous update already did this, skip the whole section. **
  You can tell in one look: your install folder is under
  C:\ProgramData\LandAllocation and your .env already contains a
  COMPOSE_PROJECT_NAME line.

  You need: an administrator login, and the external backup drive to
  hand. The drive is used twice, at M2 and again at M9.

  Why: anything on the Desktop is one accidental drag from the Recycle
  Bin, and resetting a Windows profile takes that Desktop with it. When
  this is done both folders live in

      C:\ProgramData\LandAllocation

  which is not a place anyone opens by accident. It does not appear in
  Explorer's sidebar and you reach it by typing the path — that is the
  point of it, not a problem with it.

  ** NOT "C:\Program Files". ** That looks like the tidy place and it is
  the wrong one: Windows keeps it read-only, so the app could not save a
  scanned document or write a backup into it. ProgramData is the same
  idea for the part that has to be written to.


  ** DO STEP M1 BEFORE YOU MOVE ANYTHING. **

  Docker names the app — and its database — after the folder it is
  started from. That is the warning at the top of this sheet, and it is
  what makes moving the folder dangerous. M1 writes that name down
  inside your .env file so it stops depending on the folder at all.
  After M1 the folder can sit anywhere and be called anything, today
  and every time after.


STEP M1.  Open PowerShell in your CURRENT install folder and type:

              docker compose ls

          Copy the word under NAME exactly, capital letters and all.

          (If nothing is listed, the app is not running. Start it with
           docker compose up -d and try again — this command only
           shows what is up.)

          Open .env in Notepad, click at the very end of the LAST line,
          and press ENTER once before typing. Then type:

              COMPOSE_PROJECT_NAME=the-word-you-copied

          ** Press ENTER first, every time. ** If the file did not
          already end in a blank line, typing straight away glues your
          new setting onto the end of the line above it. Both settings
          are then wrong and neither reports an error. Look at it
          before you save: COMPOSE_PROJECT_NAME must start at the very
          left of a line of its own.

          Save it. Then prove it took, in the same folder:

              docker compose ps

          ** This must be `ps`, not `ls`. ** `ls` lists the projects
          that are RUNNING, and they keep the name they were started
          under — so it reads correctly even when the line you just
          typed is misspelt. `ps` works out the name from .env as it
          stands now and shows that project's containers.

          You must see your services listed — backend, db, redis,
          worker, nginx. An empty table means the name is mistyped:
          nothing is broken and nothing is lost, the app is still
          running under its real name. Fix the spelling and run it
          again. Do not go on until you see the services.

STEP M2.  Back up, exactly as in step 2:

              docker compose exec backend python manage.py backup_db

          Then copy db-backups onto the external drive again. It is a
          fresh dump and it is the only one taken after the update —
          a backup still sitting on this computer does not protect you
          from anything you are about to do to this computer.

          ** Leave the drive plugged in, or keep it beside you. ** You
          need it once more at STEP M9, and that step is the one people
          skip when the drive has already gone back in the cupboard.

STEP M3.  Stop the app. This deletes nothing:

              docker compose down

STEP M4.  In File Explorer, click the address bar, type this and press
          Enter:

              C:\ProgramData

          Make a new folder there named exactly:

              LandAllocation

          (Windows may ask you to confirm with an administrator
           password. That is expected here and it is the whole reason
           this folder is safer than the Desktop.)

STEP M5.  Move BOTH of these into that new folder — cut and paste, or
          drag them:

              your install folder        (the one with .env in it)
              Desktop\LandAllocationData

          ** Do not rename LandAllocationData. ** STEP M6 writes its
          path into .env by that exact name.

          The install folder MAY be renamed, but only because M1 is
          done: its name stopped being the database's identity the
          moment COMPOSE_PROJECT_NAME went into .env. The bundle folder
          carries a version in its name, which is wrong the day the
          next update lands, so a plain name is worth it:

              app

          When you are done, C:\ProgramData\LandAllocation holds two
          folders and the Desktop holds neither.

          Windows will ask you to confirm the move as an administrator,
          once per folder. Say yes. If it instead says a file is in
          use, the app is still running — go back to STEP M3.

STEP M6.  Tell the app where the archive went. Open .env again — it
          moved with the install folder — and find the line that
          begins:

              DATA_ROOT=

          Replace that WHOLE line with:

              DATA_ROOT=C:/ProgramData/LandAllocation/LandAllocationData

          Forward slashes, exactly as printed. Not backslashes. No
          quotes, no spaces, and no slash on the end.

          ** A mistake here does not produce an error message. ** Docker
          quietly creates whatever folder you named and mounts that
          instead — empty. The app starts, looks perfectly healthy, and
          every existing document refuses to open, because they are all
          still sitting in the real folder. That is what check 4 below
          is for. Read this line back against the screen before saving.

STEP M7.  Close the old PowerShell window — it is still pointing at a
          folder that no longer exists. Open a new one in the install
          folder AT ITS NEW ADDRESS (Explorer, address bar, type the
          path; then SHIFT + right-click, "Open PowerShell window
          here") and start the app:

              docker compose up -d

          Give it about a minute.

STEP M8.  Put the backups back within easy reach. Right-click this
          folder:

              C:\ProgramData\LandAllocation\LandAllocationData\db-backups

          and choose  Send to  ->  Desktop (create shortcut).

          That shortcut is what you open on backup day. If someone
          deletes the shortcut it costs nothing at all — the folder
          it points at is untouched. That is the whole idea.


  NOW CHECK IT, IN THIS ORDER

  ** Do all five of these BEFORE steps M9, M10 and M11. Finishing the
     move before hiding and locking means you are never troubleshooting
     something you cannot see, and never blaming a rule you set five
     minutes ago for a problem it did not cause. **

  1. Type:  docker compose ps
     All the services are listed and say running or healthy. This also
     proves .env is being read from the new address.

  2. Open  http://localhost/   — the footer still reads
     ${APP_VERSION} (build ${APP_BUILD})

  3. Log in and open the case list. YOUR CASES MUST ALL BE THERE.

  4. Open one existing case and check its documents still open.

  5. This one matters most, because it is the only step that proves
     the app can still WRITE where it now lives:

         docker compose exec backend python manage.py backup_db

     It must succeed, and the new dump must appear under

         C:\ProgramData\LandAllocation\LandAllocationData\db-backups

     Use this rather than uploading a test document: the archive and
     the backups sit on the same mount, so writing one proves the
     other — and it costs no case number. (Case numbers are issued in
     order and are never reissued, so a test case spends one for good.)

  ** If the case list is empty, or the backup will not write: STOP.
     Do not type anything in, do not create anything. Nothing is lost,
     and both of those have a written fix — see "IF SOMETHING GOES
     WRONG" near the end of this sheet, under "The case list is empty
     AFTER moving the folders" and "Documents will not open after
     moving the folders". Do not go on to M9 until it is right. **


STEP M9.  Put the CORRECTED .env on the external drive.

          ** This is the step everybody forgets, and it is the one
             that costs you the whole system. **

          You changed .env twice today: COMPOSE_PROJECT_NAME in M1 and
          DATA_ROOT in M6. The copy of .env on your backup drive is
          now the OLD one. That copy is not a spare file — it holds
          the database password, and a backup cannot be opened without
          it. Restore from the drive as it stands and you get an app
          pointed at a database name that no longer exists, looking
          for the archive on a Desktop that no longer has it.

          So: plug the drive in and copy the .env file from

              C:\ProgramData\LandAllocation\<install folder>\.env

          over the copy already on the drive, beside the images.

          Do this on BOTH drives if you rotate two. Anywhere else .env
          is kept — a printout, a second USB stick, the safe — is also
          out of date now and should be replaced.


STEP M10. Now make the folder invisible to everyone else on this
          computer. The checks above must have passed first.

          Open PowerShell as Administrator (Start menu, type
          PowerShell, right-click it, "Run as administrator") and
          type this one line:

              attrib +h +s "C:\ProgramData\LandAllocation"

          The folder disappears from Explorer. It is still there and
          it still works — this changes nothing about who may read or
          write it, only who is shown it. Even a user who turns on
          "Hidden items" in Explorer will not see it.

          You reach it from now on in one of two ways:
              - the Desktop shortcut from step M8, or
              - typing the full path into Explorer's address bar.

          ** Be honest with yourself about what this does. ** It hides
          the folder; it does not defend it. Somebody who knows the
          path can still delete it. If you want it actually protected
          rather than out of sight, that is a permissions change and
          it is a different job — ask the developer for it.

          To undo it at any time, same window:

              attrib -h -s "C:\ProgramData\LandAllocation"


STEP M11. And last: stop anyone deleting the two folders by accident.
          In the SAME Administrator PowerShell window, one line:

              icacls "C:\ProgramData\LandAllocation" /deny "Users:(DE,DC)"

          It answers with two lines:

              processed file: C:\ProgramData\LandAllocation
              Successfully processed 1 files; Failed processing 0 files.

          "Failed processing 0 files" is the part to read.

          If it instead says "No mapping between account names and
          security IDs", this Windows is not in English and the group
          has a translated name. Use the universal form, which works
          on any language:

              icacls "C:\ProgramData\LandAllocation" /deny "*S-1-5-32-545:(DE,DC)"

          What it does, exactly: nobody signed in to this computer can
          delete the LandAllocation folder, or the two folders inside
          it. That is all it does.

          What it does NOT do — and this is the part that matters:
          it does not touch reading or writing ANYWHERE. The app goes
          on saving scanned documents and writing backups exactly as
          before, and the office goes on copying db-backups to the
          external drive exactly as before. Everything inside
          documents\ and db-backups\ stays completely normal.

          The two together are the whole point: step M10 means nobody
          finds the folder, step M11 means that if somebody does find
          it, they still cannot drag it to the Recycle Bin.

          To undo it, same window:

              icacls "C:\ProgramData\LandAllocation" /remove:d "Users"

          ** You must undo it before you ever deliberately move or
             remove these folders again — including an administrator.
             A deny beats every permission an account otherwise has,
             so Windows will refuse you too, and the refusal looks
             like a broken computer rather than a rule you set. **


  FROM NOW ON

  The app lives in       C:\ProgramData\LandAllocation\<install folder>
  The archive lives in   C:\ProgramData\LandAllocation\LandAllocationData

  The other sheets on this drive — INSTALL.txt, restore.md and
  .env.example — have all been corrected to these paths already, so
  nothing you read on this drive still points at the Desktop. Any
  OLDER printout does: treat "Desktop\LandAllocationData" in one of
  those as meaning the second path above.

  The next update is run the same way as this one, just started from
  the new address.

  Both are invisible in Explorer after step M10, and neither can be
  deleted after step M11. Nothing is wrong when you cannot see them:
  type the path into the address bar, or use the Desktop shortcut.

  ** Tell whoever runs the next update that the folder is hidden and
     locked. ** Someone who does not know that opens Explorer, sees no
     app, and concludes it was uninstalled.


------------------------------------------------------------------------
  WHAT IS NEW IN THIS VERSION
------------------------------------------------------------------------

  From the notes you sent after using 1.3.0:

  DATES
  - Every date box now reads DAY / MONTH / YEAR on every computer.
    Before, the order came from a Windows setting, not from the app, so
    it could differ from machine to machine. It cannot any more.
  - Click a box and the whole of it is selected, so typing replaces it.
    Left and right arrows move between day, month and year; up and down
    change the value; a single digit gains its zero (5 becomes 05).
  - A calendar button sits at the end of every date box.

  MUNICIPALITY FORM AND LETTER
  - The slot now counts PAGES, not files. Two one-page scans and one
    two-page scan both read as complete. Before, filing the pair as one
    file said "1 of 2" and sent you looking for a paper already in.

  OUT-OF-CITY ROWS (STEP 3)
  - The rows no longer swap places while you type in one of them.
  - A new row starts EMPTY with a placeholder instead of being filled in
    with "New institute". The step will not complete until you name it.

  SEARCHING
  - The search box on Processes now also finds a case by its LAND
    NUMBER, as well as by name, national ID and case code.

  NATIONAL ID
  - Up to 12 digits, rather than exactly 12. Shorter IDs are accepted.

  OLD CASES — A NEW BUTTON
  - "Old allocation", beside "New allocation" on the Processes screen.
    It takes a name, national ID, mother's name, date of birth,
    category, land number, and ONE PDF: the whole case file.
  - The case gets the next case number, exactly as a new one does.
    Nothing is typed for the number.
  - Its five steps stay empty on purpose, and the case is marked
    "Entered from paper" so nobody mistakes it for unfinished work.
  - The duplicate checks still run. A national ID already on file is
    refused here just as it is on the ordinary form.

  ** This build also carries the fix from build 5 (letters and lists
     failing with "permission denied"). If you already ran the repair
     command by hand, nothing changes for you there. **


  From your own testing in the office:

  IDENTITY CARDS
  - A card's two sides are now ONE file, whether you scan them or import
    them. One row on the screen, one file in the folder, front and back
    as page 1 and page 2.
  - Both sides can be picked at once when importing. One at a time
    still works exactly as before.
  - A card with both sides now says "both sides" instead of counting.
  - Deleting a card removes the whole card, both sides together.
  - Cards already on file as two separate documents are left exactly as
    they are. Only cards filed from now on are joined.

  THE NATIONAL ID
  - It must be exactly 12 numbers, for the beneficiary and the spouse,
    whether typed in or read from a card. The box refuses anything else
    as you type.
  - Numbers written in Kurdish/Arabic digits are accepted and stored as
    ordinary digits, so the duplicate check can still see them.
  - ** Records already on file are not affected. ** You can still
    correct the phone number of a beneficiary whose ID was entered
    before this rule. Only an ID you actually change must be 12 digits.

  FILES ON DISK
  - Saved files no longer carry random letters and numbers. A file is
    named for what it is, and a second file in the same slot is
    numbered — the way Windows numbers a copy.
  - Generated letters and lists are NOT kept any more. They are made,
    you print or save them, and they are gone. Nothing generated sits
    in your document folder or in a backup. The compiled case file from
    step 5 is still kept, exactly as before.

  DATES
  - Step 4 now ends on the date of its LAST institute to decide, the
    same way step 3 already did.
  - The closing date in step 5 is accepted as you type it, including a
    date earlier than the day you marked the case complete.

  THE SCREENS
  - A new case is assigned to whoever opens it.
  - An institute row starts on the lawyer the case belongs to, instead
    of nobody.
  - The out-of-city institute name has room for the whole name.
  - In step 4 the municipality form sits with the other file boxes.
  - The button back to the case list is easier to see.


------------------------------------------------------------------------
  THINGS TO DO AFTER THE UPDATE
------------------------------------------------------------------------

  1. DELETE THE OLD "_generated" FOLDER

  Until this version, letters and lists were written into your document
  folder. They are not any more — but the old ones are still sitting
  there, and they will stay in every backup you take from now on. They
  are copies of beneficiaries' details that nothing needs.

  In File Explorer, open

      C:\ProgramData\LandAllocation\LandAllocationData\documents

  and delete the folder named

      _generated

  ** This is safe. ** Nothing in the app points at anything inside it:
  it only ever held letters and lists, each of which is produced again
  by pressing Generate. Your case documents are in the folders beside
  it, named for the case — do not touch those.

  (If there is no `_generated` folder, nothing was left behind and
   there is nothing to do.)


  2. FILL IN THE INSTITUTE ROWS THAT NAME NOBODY

  Institute rows filed BEFORE this version recorded no lawyer at all,
  so the case file prints a blank where a name belongs. One command
  fills them in from the lawyer each case belongs to.

  Do it AFTER the checks above have passed, in the same PowerShell:

      docker compose exec backend python manage.py backfill_entry_lawyers

  It only REPORTS. It tells you how many rows are blank and changes
  nothing. Then, to actually fill them in:

      docker compose exec backend python manage.py backfill_entry_lawyers --apply

  It never touches a row that already names someone, so an institute a
  colleague handled keeps saying so. Running it twice does nothing the
  second time.


  3. REMOVE THE OLD COMPILED CASE FILES  (from build 7)

  Until this version, closing a case stored its compiled file — every
  paper on the case, merged again — in the case's folder, so a finished
  case took about twice the space it needed. The app no longer keeps
  that file: pressing "Compile" produces it fresh whenever it is needed.

  One command removes the copies stored before. First, see what it
  would do:

      docker compose exec backend python manage.py retire_compiled_exports

  It only REPORTS — how many files, how many cases, how many MB. Then,
  to actually remove them:

      docker compose exec backend python manage.py retire_compiled_exports --apply

  ** It never touches a case file you scanned in through the backlog
  page. ** Those are the only copy of that paper case and stay exactly
  where they are. Only files the app itself produced are removed, and
  each one is recorded in the activity log. Running it twice does nothing
  the second time.


------------------------------------------------------------------------
  IF SOMETHING GOES WRONG
------------------------------------------------------------------------

  Is everything up?
      docker compose ps
      Every line should say "running" or "healthy".

  What went wrong?
      docker compose logs backend --tail 50

  Is the app healthy?
      Open  http://localhost/api/v1/health/
      Every item must say "ok".

  Nothing at all responds:
      docker compose down
      docker compose up -d

  The case list is empty AFTER moving the folders
      This is the one failure the MOVING section is built to prevent,
      and it is recoverable. Nothing has been deleted. The app is
      looking for a database under a name that has never existed,
      while yours sits untouched under its old name.

      ** Do not create a case, a user or a category. Do not "start
         again" and do not run create_admin. Writing into the empty
         database is what turns a five-minute fix into a hard one. **

      1.  docker compose down

      2.  docker volume ls

          Look for the names ending in  _db_data . Your real database
          is the one whose name does NOT match the project name you
          are currently using.

      3.  Open .env and set COMPOSE_PROJECT_NAME to the word that sits
          in front of _db_data on that line — exactly, character for
          character.

      4.  docker compose up -d

      Your cases come back. If they do not, stop there and call the
      developer — do not delete a volume to tidy up. A volume you
      delete is gone for good, and one of those two is everything.

  Documents will not open after moving the folders
      DATA_ROOT in .env is pointing somewhere that is not the real
      archive — usually a typo, a backslash, or a trailing slash.
      Docker made that folder rather than complaining. Fix the line
      (STEP M6), then  docker compose down  and  docker compose up -d .
      Nothing was lost: the files never moved from the real folder.

  Windows refuses to move, rename or delete the folders
      That is step M11 doing its job, not a fault, and it refuses an
      administrator too. Lift it, do the work, put it back:

          icacls "C:\ProgramData\LandAllocation" /remove:d "Users"
          ...
          icacls "C:\ProgramData\LandAllocation" /deny "Users:(DE,DC)"

  Going back to the old version is possible and your backup from
  step 2 is what does it. Call the developer rather than trying it
  from memory.


------------------------------------------------------------------------
  TICK-LIST
------------------------------------------------------------------------

  [ ] 1. PowerShell open in the CURRENT install folder
  [ ] 2. backup_db run, db-backups AND documents copied to the drive
  [ ] 3. docker compose ls — NAME written down
  [ ] 4. docker compose down
  [ ] 5. Four things copied in (.env NOT touched)
  [ ] 6. docker load / up -d / migrate
  [ ] 7. docker compose ls — NAME is the same
  [ ] 8. Footer reads ${APP_VERSION} (build ${APP_BUILD})
  [ ] 9. All cases still listed, one case opened and checked
  [ ] 10. the old `_generated` folder deleted from documents\
  [ ] 11. backfill_entry_lawyers run with --apply (see the section above)
  [ ] 12. retire_compiled_exports run with --apply (from build 7; see above)

  Only if you also did the MOVING section:

  [ ] M1. COMPOSE_PROJECT_NAME written into .env, docker compose ps
          still lists the services
  [ ] M2. backup_db run
  [ ] M3. docker compose down
  [ ] M4. C:\ProgramData\LandAllocation created
  [ ] M5. Both folders moved in, LandAllocationData NOT renamed
  [ ] M6. DATA_ROOT line replaced, forward slashes
  [ ] M7. docker compose up -d from the new address
  [ ] M8. Desktop shortcut to db-backups made
  [ ] --  ALL FIVE CHECKS passed: services listed, footer right, all
          cases listed, one old case's documents still OPEN, and
          backup_db writing into the new folder
  [ ] M9. Corrected .env copied onto the external drive(s) — the
          one with COMPOSE_PROJECT_NAME and the new DATA_ROOT in it
  [ ] M10. attrib +h +s run — folder no longer visible
  [ ] M11. icacls deny run — "Failed processing 0 files"
  [ ] --  One last look: app still opens, backup_db still writes
