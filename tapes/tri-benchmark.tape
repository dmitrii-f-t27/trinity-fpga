# VHS tape for tri benchmark
# Key demo: benchmark suite for addressing speed objections (the old "63 tok/s" caption is withdrawn: tri benchmark prints no tok/s figure)

Output tri-benchmark.gif
Set FontSize 26
Set Width 1400
Set Height 700
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms

# Start with clean terminal
Type "cd ~/trinity-fpga"
Enter
Sleep 500ms

# Show git status first
Type "git status"
Enter
Sleep 1s

# Run full benchmark suite
Type "tri benchmark"
Enter
Sleep 8s

# Show individual component benchmarks
Type "tri benchmark vsa"
Enter
Sleep 4s

Type "tri benchmark vm"
Enter
Sleep 4s
