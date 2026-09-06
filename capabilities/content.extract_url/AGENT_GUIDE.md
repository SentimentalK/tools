# Agent Execution Guide for Capability: content.extract_url

## CRITICAL INSTRUCTIONS - READ CAREFULLY
1. You are acting as an automated, non-interactive execution worker.
2. DO NOT enter plan mode.
3. DO NOT search, explore, inspect, or modify any files across this repository or any workspace.
4. DO NOT attempt to write or transcribe subtitles yourself.
5. Execute the EXACT command specified below using `run_command`:

```bash
{{RUN_ENTRYPOINT}} --input "{{INPUT_JSON_PATH}}" --output-dir "{{OUTPUT_DIR}}"
```

6. Once the command finishes execution, exit and stop calling any more tools immediately.
