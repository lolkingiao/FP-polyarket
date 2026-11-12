#!/bin/zsh
echo "=== process ==="
ps aux | grep "record.py" | grep -v grep || echo "no record.py process running"
echo ""
echo "=== file count ==="
ls data/snapshots/round1_design/ 2>/dev/null | wc -l
echo ""
echo "=== distinct windows ==="
ls data/snapshots/round1_design/ 2>/dev/null | awk -F'_' '{print $2}' | sort -u | wc -l
echo ""
echo "=== resume log tail ==="
tail -10 data/snapshots/round1_design_resume.log 2>/dev/null || echo "resume log not found"
echo ""
echo "=== skip count ==="
grep -c "\[skip\]" data/snapshots/round1_design_resume.log 2>/dev/null || echo "0"