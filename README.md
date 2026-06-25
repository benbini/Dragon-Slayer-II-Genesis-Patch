# Dragon-Slayer II Genesis Text Insertion Package

## Motivation

   This is a port of a set of [tools](https://www.romhacking.net/abandoned/%5B42%5Ddragon_slayer_2.rar) listed on the "Abandoned" Section of Romhacking.net for patching the Genesis version of Legend of Heroes II (Dragon Slayer - Eiyuu Densetsu II) into English and other languages.  I've long wanted to play the game in English and have modernized the tools, using AI to port C++ code to Python and batch scripts to bash, in the hopes that doing so will enable interested people, particularly those who prefer to work in Linux/MacOS environments as opposed to Windows, to finish the work that the anonymous coder(s) responsible for the abandoned tools started. 

## Credits

   I must emphasize that I am directly responsible for very little of the code in this repository.  My contribution consists almost entirely of using ChatGPT 5.5-medium thinking to port the C++ source found in the Romhacking-hosted toolset to equivalent Python, and correcting a mercifully-few number of bugs that were introduced during that process.  The extremely simple bash scripts and two Python scripts, `dump_lines.py` and `insert_asm.py`, are my own work.  Obviously a huge thank-you to whoever put these tools together in 2007.  Without their work it would be impossible to even be thinking about resuming efforts to patch this game now.

   The original Romhacking toolset uses a very old version, marked 1.06, of the [Atlas](https://github.com/stevemonaco/Atlas) text insertion framework, led by Steve Monaco and Gideon Zhi.  According to Steve Monaco this 1.06 code has undergone some revision by the authors of the ported toolset.  I would like to thank Steve Monaco for allowing me to host a Python port of a (very ancient version) of his code.

   The original toolset also uses a fork of Byuu's XKAS assembler apparently targeting the Gameboy Color; I was unable to find source for that specific assembler but fortunately the assembler was used for extremely simple insertion of assembly into the ROM that I simply re-coded in `insert_asm.py`.  
   
## Prerequisites

   The Python scripts require at least Python 3.13 to run.

   You must also have a legally acquired ROM image of the Legend of Heroes II ROM for Genesis:

```text
       CRC32: 46924dc3
       MD5:   4c1a1583bd29071300fd1488aa7d0cc1
       SHA1:  79b6201301acb5d9e9c56dcf65a9bcf9d9a931ab
```
   Place this ROM in the `ref` folder, using any name you please.  The ROM will never be altered in this location.

## Usage

   The following assumes that a ROM is present directly under the `ref` folder.
   
   1. First run `dump_text.sh`.  This will create a number of folders including `text` under which you should find a series of `script_XX.txt` files containing unpacked script data.  If you simply want to dump the text from these scripts for translating, run `dump_lines.py`.  This will dump the shift-jis Japanese in the files into an Excel spreadsheet which can then be uploaded to Google Sheets or otherwise done with as you please.

   2. Then run `copy_image.sh`.  I confess that I have not investigated what this does.

   3.
      a. Before you can run `insert_text`, you need to have a translated script file.  For experimentation I recommend focusing on `script_2E.txt`, which contains the earliest script data in the game I've been able to discover (section 002416 specifically has the _very_ first scripted dialogue).  I (again) used ChatGPT to machine-translate this file with little trouble.  An important note is that at least currently the replacement text MUST BE IN WIDE CHARACTER NOT ASCII, otherwise Atlas will generate errors during the insertion process.  

      b. Once you have a script file, insert it in the `script_inserts` folder.  Then run `insert_text`, which will either re-insert existing game files (erroring out while doing so, because they're full of Japanese) or replace the original file(s) with whatever it finds in `script_inserts`.

   4. You can now run `insert_binary`, which as far as I can tell will pack the scripts into the `.bin` files, recompress these files, and reinsert them into the ROM.

   5. Finally, patch the assembly: `python3 insert_asm.py modded_dslayer2_work.bin ref/asm1.bin ref/asm2.bin`

This is rather a lot to keep track of, so I've provided an orchestration script that goes through all this for you.  I recommend using `clean.sh` as well to reset your working environment to a working initial state.  However you are probably going to want to stick to Steps 1-3 for a while.

All C++ source from the original toolset is included under `c_src` for convenient reference in the likely case problems crop up.

## Limitations

It is important to note that the Romhacking toolset was clearly left incomplete: most notable is the lack of a batch script to dump the bitmap data, which I am guessing includes a rather large amount of text that scrolls as part of the introduction to the game (you will get very, VERY tired of the long cutscenes before script data starts displaying).  The Romhacking toolset does include a font (un)packer that I didn't bother to port because it appears very simple, and easy to port down the road.

I did compare the behavior of these ported tools to their Windows originals and was able to verify, via hash checks, that behavior through and including Step 3, `insert_text`, is identical across environments.  Modifying and compressing the `bin` images in Step 4 also appears to mirror the Windows process exactly, however the resultant ROM images currently diverge slightly for as-yet unknown reasons.  It is unknown whether this divergence might introduce problems at some point, but it does not appear to affect the rendering of inserted text.

I have not done any analysis on whether/how data for non-dialogue, such as shop items and interfaces, is included in the script files.  
   
