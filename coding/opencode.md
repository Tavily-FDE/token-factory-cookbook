# Using OpenCode with Token Factory

[OpenCode](https://opencode.ai/) offers excellent support for Token Factory

- [Option 1: Native support](#option-1-native-support)
- [Option 2: Add Token Factory as a custom provider](#option-2-also-add-a-custom-provider)
- [Option 3: Use a proxy](#option-3-using-a-proxy)
- [Guides and resources](#guides--resources)

## Option 1: Native support

Easiest.

1. Within OpenCode, use `/connect`
2. Select `Nebius Token Factory` as provider
3. Enter API key when prompted.
4. Use `/models` to select a model
5. That's it!

[🎥 howto video](https://www.youtube.com/watch?v=216_T--JE0k)

## Option 2: Also add a custom provider

This is a handy option for newer models that don't appear in the catalog.

1. Define a custom provider in `opencode.jsonc`.  
   The file is usually at `~/.config/opencode/opencode.jsonc`
2. Use this example snippet. You can also find examples here: [example 1](opencode.jsonc.example1) and [example 2](opencode.jsonc.example2)
   ```json
   {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "nebius-token-factory-custom": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Nebius Token Factory (Custom)",
                "options": {
                    "baseURL": "https://api.tokenfactory.nebius.com/v1"
                },
                "models": {
                    "zai-org/GLM-5.3-Flash": {
                        "name": "GLM-5.3-Flash",
                        "tool_call": true,
                        "reasoning": true,
                        "limit": {
                            "context": 1048576,
                            "output": 1048576
                        },
                        "cost": {
                            "input": 0.15,
                            "output": 0.5
                        }
                    }
                }
            }
        }
   }
   ```
3. Restart `opencode`
4. Use `/connect` to the custom provider we just defined, e.g. `Nebius Token Factory (Custom)`
5. Enter API key
6. Use `/models` to select the models defined for this provider!


## Option 3: Using a proxy

Use this proxy: [Nebius TF Relay](https://nebius-tf-relay.vercel.app/)

## Guides & Resources

- A [setup guide](https://github.com/m1burn/omo-nebius-token-factory) for agentmemory + OpenCode + Token Factory