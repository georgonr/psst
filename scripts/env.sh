# Source me: local toolchain paths for PSST builds (see BUILD.md)
export PATH="$HOME/.local/node-v24.22.0-darwin-x64/bin:$HOME/.local/bin:$PATH"
export JAVA_HOME="$HOME/.local/jdk-21.0.13+9/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_HOME="$HOME/Library/Android/sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
export NX_NO_CLOUD=true
export NX_DEFAULT_OUTPUT_STYLE=stream-without-prefixes
