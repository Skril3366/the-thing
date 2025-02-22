# The(sis) Thing

> ThenThing script helps you to complete literature review process of paper
> writing by using LLMs


## Configuration and Requirements

All the required settings should be configured via
[config.py](./src/common/config.py) file


## Usage

Preparation:
1. Firstly you need to fill the correct information into all the varibales in config file (see requirements)
2. Then you can click "Export Collection" in Zotero and export it directly into
   references folder (if config for folders remains the same)
3. And lastly you need to export json file with references from Zotero and configure its location

Now you can run the script and see the magic happen. All the important decisions
are left out for you in yes/no questions. If you want to respond all `yes` to
them just use `--all` flag

```bash
poetry run python ./src/the_thing.py
```

After the script finishes grap `notes` directory (specified through the config
file) and do whatever you want next

For e.g. you can use obsidian with copilot plugin for working with those ideas

NOTE: script assumes that already processed papers don't have to be processed again. If this is not the case you must manually delete the directory you want to process again

## How it works in a nutshell

1. You collect all your pdfs into a single folder. For e.g. by exporting from Zotero
2. Algorithm extracts text from those pdfs
3. Then it provides LLM with text + prompt to create notes. Prompt makes LLM create atomic notes, each note containing only a single idea (for more details explore source code of the prompts)
4. All the notes get saved
5. Then you are free to do anything you want with them. For e.g. you can import them into obsidian with copilot plugin, which indexes them into vector db and then you can chat with those ideas
