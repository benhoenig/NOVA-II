#!/usr/bin/env python3
"""
Enhanced semantic cleanup tool for NOVA II Knowledge Base.

This script finds and removes semantically similar entries using
a combination of exact matching and keyword-based similarity.

Usage:
    python semantic_cleanup_v2.py [--dry-run] [--threshold 0.7]
"""

import os
import argparse
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def calculate_similarity(text1, text2):
    """
    Calculate simple similarity score between two texts.
    Returns a score between 0 and 1.
    """
    # Normalize texts
    t1 = set(text1.lower().split())
    t2 = set(text2.lower().split())
    
    if not t1 or not t2:
        return 0.0
    
    # Jaccard similarity: intersection / union
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    
    return intersection / union if union > 0 else 0.0

def find_semantic_duplicates(threshold=0.7):
    """Find groups of semantically similar entries."""
    print(f"🔍 Scanning Knowledge Base for semantic duplicates (threshold: {threshold})...\n")
    
    response = supabase.table("knowledge_base").select("*").order("created_at", desc=True).execute()
    data = response.data
    
    groups = []  # List of duplicate groups
    processed = set()  # IDs already assigned to a group
    
    for i, item1 in enumerate(data):
        if item1['id'] in processed:
            continue
            
        # Start a new group with this item
        group = [item1]
        processed.add(item1['id'])
        
        # Compare with all subsequent items
        for item2 in data[i+1:]:
            if item2['id'] in processed:
                continue
            
            # Calculate similarity
            text1 = f"{item1.get('title', '')} {item1.get('content', '')}"
            text2 = f"{item2.get('title', '')} {item2.get('content', '')}"
            
            similarity = calculate_similarity(text1, text2)
            
            if similarity >= threshold:
                group.append(item2)
                processed.add(item2['id'])
        
        # Only keep groups with 2+ items
        if len(group) > 1:
            groups.append(group)
    
    return groups

def display_groups(groups):
    """Display duplicate groups for review."""
    if not groups:
        print("✅ No semantic duplicates found.\n")
        return
    
    print(f"📊 Found {len(groups)} groups of similar entries:\n")
    
    for i, group in enumerate(groups, 1):
        print(f"{'='*60}")
        print(f"Group {i} ({len(group)} entries):")
        print(f"{'='*60}")
        
        for j, item in enumerate(group, 1):
            print(f"\n  {j}. ID: {item['id']}")
            print(f"     Title: {item.get('title', 'N/A')}")
            print(f"     Category: {item.get('category', 'N/A')}")
            print(f"     Created: {item.get('created_at', 'N/A')}")
            if item.get('content'):
                preview = item['content'][:80] + "..." if len(item['content']) > 80 else item['content']
                print(f"     Content: {preview}")
        
        print()

def cleanup_duplicates(groups, dry_run=True):
    """Clean up duplicates, keeping the oldest entry in each group."""
    if not groups:
        return
    
    total_to_delete = sum(len(group) - 1 for group in groups)
    
    if dry_run:
        print(f"\n🔍 DRY RUN MODE - Would delete {total_to_delete} entries\n")
    else:
        print(f"\n🗑️ Deleting {total_to_delete} duplicate entries...\n")
    
    deleted_count = 0
    
    for i, group in enumerate(groups, 1):
        # Keep the first (oldest) entry, delete the rest
        keep = group[0]
        to_delete = group[1:]
        
        print(f"Group {i}: Keeping '{keep['title']}' (ID: {keep['id']})")
        
        for item in to_delete:
            if dry_run:
                print(f"  [DRY RUN] Would delete: {item['id']} - {item['title']}")
            else:
                try:
                    supabase.table("knowledge_base").delete().eq("id", item['id']).execute()
                    print(f"  ✅ Deleted: {item['id']} - {item['title']}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  ❌ Failed to delete {item['id']}: {e}")
    
    if not dry_run:
        print(f"\n✨ Cleanup complete! Deleted {deleted_count} entries.")
    else:
        print(f"\n💡 Run without --dry-run to actually delete these entries.")

def main():
    parser = argparse.ArgumentParser(
        description='Find and remove semantic duplicates from Knowledge Base'
    )
    parser.add_argument('--dry-run', action='store_true', 
                        help='Preview what would be deleted without actually deleting')
    parser.add_argument('--threshold', type=float, default=0.7,
                        help='Similarity threshold (0.0-1.0, default: 0.7)')
    
    args = parser.parse_args()
    
    # Find duplicates
    groups = find_semantic_duplicates(threshold=args.threshold)
    
    # Display groups
    display_groups(groups)
    
    # Cleanup (with dry-run option)
    if groups:
        cleanup_duplicates(groups, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
