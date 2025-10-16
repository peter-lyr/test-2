import os
import sys
import subprocess
import shutil
from collections import defaultdict

COMMIT_INFO_FILE = ""
EXE_NAME = "git-merge-split-files.exe"


def split_large_file(file_path, chunk_size=50 * 1024 * 1024):
    """拆分大文件为多个小文件"""
    try:
        file_dir, file_name = os.path.dirname(file_path), os.path.basename(file_path)
        base_name, file_ext = os.path.splitext(file_name)
        split_dir = os.path.join(file_dir, f"{base_name}{file_ext}-split")
        os.makedirs(split_dir, exist_ok=True)
        with open(file_path, "rb") as f:
            chunk_num = 1
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunk_file = os.path.join(
                    split_dir, f"{base_name}{file_ext}-part{chunk_num:04d}"
                )
                with open(chunk_file, "wb") as chunk_f:
                    chunk_f.write(chunk)
                chunk_num += 1
        print(f"✅ Split {file_path} into {chunk_num-1} parts")
        return True
    except Exception as e:
        print(f"❌ Error splitting file {file_path}: {e}")
        return False


def get_file_size_mb(file_path):
    """获取文件大小（MB）"""
    try:
        return os.path.getsize(file_path) / (1024 * 1024)
    except OSError:
        return 0


def find_large_files(directory, min_size_mb=50):
    """递归查找目录中所有大于指定大小的文件"""
    large_files = []
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                size_mb = get_file_size_mb(file_path)
                if size_mb > min_size_mb:
                    large_files.append((file_path, size_mb))
    except Exception as e:
        print(f"❌ Error scanning directory {directory}: {e}")
    return large_files


def process_large_untracked_files():
    """处理所有超过50MB的未跟踪文件和文件夹中的大文件"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        large_files, processed_dirs = [], set()
        for line in result.stdout.strip().split("\n"):
            if not line.strip() or not line.startswith("??"):
                continue
            item_path = line[3:].strip().replace('"', "")
            if " -> " in item_path:
                item_path = item_path.split(" -> ")[1]
            if os.path.isfile(item_path):
                size_mb = get_file_size_mb(item_path)
                if size_mb > 50:
                    large_files.append((item_path, size_mb))
            elif os.path.isdir(item_path):
                dir_path = os.path.normpath(item_path)
                if dir_path not in processed_dirs:
                    processed_dirs.add(dir_path)
                    large_files.extend(find_large_files(dir_path))
        if not large_files:
            return
        print(f"🔍 Found {len(large_files)} large untracked files (>50MB):")
        for file_path, size_mb in large_files:
            print(f"   {file_path}: {size_mb:.2f} MB")
            process_single_large_file(file_path)
    except Exception as e:
        print(f"❌ Error processing large untracked files: {e}")


def process_single_large_file(file_path):
    """处理单个大文件"""
    try:
        file_dir, file_name = os.path.dirname(file_path), os.path.basename(file_path)
        base_name, file_ext = os.path.splitext(file_name)
        print(f"\n📦 Processing large file: {file_path}")
        gitignore_path = os.path.join(file_dir, ".gitignore")
        gitignore_content = []
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gitignore_content = f.read().splitlines()
        patterns_to_add = [file_name, f"{base_name}{file_ext}.merged"]
        for pattern in patterns_to_add:
            if pattern not in gitignore_content:
                gitignore_content.append(pattern)
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("\n".join(gitignore_content))
        print(f"✅ Updated .gitignore in {file_dir}")
        target_exe_path = os.path.join(file_dir, EXE_NAME)
        source_exe_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), EXE_NAME
        )
        if not os.path.exists(target_exe_path) and os.path.exists(source_exe_path):
            shutil.copy2(source_exe_path, target_exe_path)
            print(f"✅ Copied {EXE_NAME} to {file_dir}")
        elif not os.path.exists(source_exe_path):
            print(f"⚠️  {EXE_NAME} not found in script directory")
        split_large_file(file_path)
    except Exception as e:
        print(f"❌ Error processing large file {file_path}: {e}")


def get_git_status():
    """获取git状态信息"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        file_list, deleted_files = [], []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            status, filename = line[:2].strip(), line[3:].strip().replace('"', "")
            if " -> " in filename:
                filename = filename.split(" -> ")[1]
            if "D" in status:
                deleted_files.append(filename)
            else:
                file_list.append(filename)
        return file_list, deleted_files
    except Exception as e:
        print(f"❌ Error getting git status: {e}")
        return [], []


def scan_directory(path):
    """递归扫描目录，返回所有文件的路径和大小"""
    file_sizes = []
    try:
        if os.path.isfile(path):
            file_sizes.append((path, os.path.getsize(path)))
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_sizes.append((file_path, os.path.getsize(file_path)))
                    except OSError:
                        continue
    except OSError:
        pass
    return file_sizes


def scan_and_categorize_files():
    """扫描并分类文件"""
    git_files, deleted_files = get_git_status()
    if not git_files and not deleted_files:
        print("📭 No modified, untracked or deleted files found")
        return {}, [], []

    all_files = []
    for file_path in git_files:
        if os.path.isdir(file_path):
            dir_files = scan_directory(file_path)
            all_files.extend(
                (f_path, size / (1024 * 1024)) for f_path, size in dir_files
            )
        else:
            all_files.append((file_path, get_file_size_mb(file_path)))

    if not all_files and not deleted_files:
        print("📭 No valid files to process")
        return {}, [], []

    dir_files_map = defaultdict(list)
    for file_path, size_mb in all_files:
        if dir_path := os.path.dirname(file_path):
            dir_files_map[dir_path].append((file_path, size_mb))

    result_dict, processed_files = {}, set()
    for dir_path in sorted(
        dir_files_map.keys(), key=lambda x: x.count(os.sep), reverse=True
    ):
        current_files = [
            (f, s) for f, s in dir_files_map[dir_path] if f not in processed_files
        ]
        if not current_files:
            continue
        total_size = sum(size for _, size in current_files)
        if total_size <= 50:
            result_dict[dir_path] = total_size
            processed_files.update(f for f, _ in current_files)
        else:
            for file_path, size_mb in current_files:
                if file_path not in processed_files:
                    result_dict[file_path] = size_mb
                    processed_files.add(file_path)

    for file_path, size_mb in all_files:
        if not os.path.dirname(file_path) and file_path not in processed_files:
            result_dict[file_path] = size_mb

    # 将已删除文件按目录分组
    deleted_files_by_dir = defaultdict(list)
    for file_path in deleted_files:
        dir_path = os.path.dirname(file_path) or "."
        deleted_files_by_dir[dir_path].append(file_path)

    return result_dict, deleted_files, deleted_files_by_dir


def run_git_commands(commands):
    """执行一系列Git命令"""
    success = True
    for cmd in commands:
        print(f"▶️  {cmd}")
        if os.system(cmd) != 0:
            print(f"❌ Command failed: {cmd}")
            success = False
    return success


def commit_batch(
    file_paths, deleted_paths, batch_total_size, batch_number, total_batches
):
    """提交一个批次的文件（包括未追踪和已删除文件）"""
    print(
        f"📦 Batch {batch_number}/{total_batches}: {len(file_paths)} files, {len(deleted_paths)} deleted files, {batch_total_size:.2f} MB"
    )

    # 处理未追踪文件
    valid_paths = []
    for path in file_paths:
        if os.path.exists(path):
            if os.path.isdir(path):
                if any(os.walk(path)):
                    valid_paths.append(path)
                else:
                    print(f"⚠️  Directory is empty: {path}")
            else:
                valid_paths.append(path)
        else:
            print(f"⚠️  Path does not exist: {path}")

    # 处理已删除文件
    valid_deleted_paths = []
    for path in deleted_paths:
        # 检查文件是否确实不存在（已被删除）
        if not os.path.exists(path):
            valid_deleted_paths.append(path)
        else:
            print(f"⚠️  File marked as deleted but still exists: {path}")

    if not valid_paths and not valid_deleted_paths:
        print("⏭️  No valid paths, skipping batch")
        return False

    # 添加未追踪文件
    successful_adds = 0
    for path in valid_paths:
        if run_git_commands([f'git add "{os.path.normpath(path)}"']):
            successful_adds += 1

    # 添加已删除文件
    successful_deletes = 0
    for path in valid_deleted_paths:
        if run_git_commands([f'git rm "{os.path.normpath(path)}"']):
            successful_deletes += 1

    print(
        f"✅ Added {successful_adds}/{len(valid_paths)} files, removed {successful_deletes}/{len(valid_deleted_paths)} files"
    )

    # 只有当有实际变更时才提交
    if successful_adds > 0 or successful_deletes > 0:
        return run_git_commands([f"git commit -F {COMMIT_INFO_FILE}", "git push"])
    else:
        print("⏭️  No changes to commit, skipping")
        return True


def commit_in_batches(files_dict, deleted_files_by_dir, total_size):
    """分批提交文件，将同一目录下的未追踪和已删除文件放在同一批次"""
    batches = []
    current_batch, current_deleted, current_size = [], [], 0

    # 创建一个包含所有目录的列表，包括有未追踪文件和已删除文件的目录
    all_dirs = set(files_dict.keys())
    for dir_path in deleted_files_by_dir.keys():
        # 如果目录中有已删除文件但没有未追踪文件，添加一个大小为0的条目
        if dir_path not in files_dict:
            files_dict[dir_path] = 0
            all_dirs.add(dir_path)

    # 按目录深度排序
    sorted_dirs = sorted(all_dirs, key=lambda x: x.count(os.sep), reverse=True)

    for dir_path in sorted_dirs:
        dir_files = []
        dir_size = 0

        # 如果是目录条目，获取该目录下所有文件
        if dir_path in files_dict and os.path.isdir(dir_path):
            for root, _, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):  # 确保文件存在
                        size_mb = get_file_size_mb(file_path)
                        dir_files.append(file_path)
                        dir_size += size_mb
        elif dir_path in files_dict:
            # 单个文件
            if os.path.exists(dir_path):
                dir_files = [dir_path]
                dir_size = files_dict[dir_path]

        # 获取该目录下的已删除文件
        dir_deleted = deleted_files_by_dir.get(dir_path, [])

        # 如果当前批次加上这个目录的内容超过100MB，开始新批次
        if current_size + dir_size > 100 and (current_batch or current_deleted):
            batches.append((current_batch.copy(), current_deleted.copy(), current_size))
            current_batch, current_deleted, current_size = [], [], 0

        # 添加目录内容到当前批次
        current_batch.extend(dir_files)
        current_deleted.extend(dir_deleted)
        current_size += dir_size

        # 如果单个目录就超过100MB，需要单独处理
        if dir_size > 100:
            print(
                f"⚠️  Directory {dir_path} exceeds 100MB ({dir_size:.2f} MB), splitting..."
            )
            # 对于大目录，我们单独提交其中的文件
            for file_path in dir_files:
                file_size = get_file_size_mb(file_path)
                if file_size <= 100:  # 跳过超过100MB的大文件，它们应该已经被处理了
                    if current_size + file_size > 100 and (
                        current_batch or current_deleted
                    ):
                        batches.append(
                            (current_batch.copy(), current_deleted.copy(), current_size)
                        )
                        current_batch, current_deleted, current_size = [], [], 0
                    current_batch.append(file_path)
                    current_size += file_size

    # 添加最后一个批次
    if current_batch or current_deleted:
        batches.append((current_batch, current_deleted, current_size))

    print(f"📋 Total batches: {len(batches)}")
    committed_size = 0

    for i, (batch, deleted, batch_size) in enumerate(batches, 1):
        if commit_batch(batch, deleted, batch_size, i, len(batches)):
            committed_size += batch_size
            print(f"✅ Completed Batch {i}/{len(batches)}")
            progress = (committed_size / total_size * 100) if total_size > 0 else 100
            print(
                f"📈 Progress: {committed_size:.2f}/{total_size:.2f} MB ({progress:.1f}%)"
            )

    return True


def execute_git_commands(files_dict, deleted_files, deleted_files_by_dir):
    """执行git命令"""
    if not files_dict and not deleted_files:
        print("📭 No files to commit")
        return False

    total_size = sum(files_dict.values())
    print(f"📊 Total size: {total_size:.2f} MB")
    print(f"🗑️  Deleted files: {len(deleted_files)}")

    if total_size <= 100 and len(deleted_files) == 0:
        print("\n🚀 Committing all files at once...")
        return run_git_commands(
            ["git add -A", f"git commit -F {COMMIT_INFO_FILE}", "git push"]
        )
    else:
        print("\n📦 Committing in batches (files and deletions together)...")
        return commit_in_batches(files_dict, deleted_files_by_dir, total_size)


def main():
    global COMMIT_INFO_FILE
    if len(sys.argv) != 2:
        print("❌ Usage: python script.py <commit-info.txt>")
        sys.exit(1)
    COMMIT_INFO_FILE = sys.argv[1]
    if not os.path.exists(COMMIT_INFO_FILE):
        print(f"❌ Commit info file '{COMMIT_INFO_FILE}' not found")
        sys.exit(1)
    print("🔍 Checking for large untracked files...")
    process_large_untracked_files()
    files_dict, deleted_files, deleted_files_by_dir = scan_and_categorize_files()
    if not files_dict and not deleted_files:
        print("📭 No files to process")
        return
    if execute_git_commands(files_dict, deleted_files, deleted_files_by_dir):
        print("\n🎉 All operations completed successfully!")
    else:
        print("\n❌ Some operations failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
