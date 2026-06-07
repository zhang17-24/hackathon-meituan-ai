"""Seed community posts with real nail art images and Chinese copy.

Usage: cd backend && uv run python scripts/seed_community_posts.py
"""
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, UTC
from pathlib import Path

# Ensure we can import from packages.harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.harness.nailflow.tools.nail.base import get_db, UPLOADS_DIR

COMMUNITY_DIR = UPLOADS_DIR / "community"
COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)

# Base path for source nail images (relative to backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NAIL_IMG_DIR = PROJECT_ROOT / "美甲图片"

# Map: source image path -> (content, tags, user_id)
# Using realistic Xiaohongshu-style copy
POSTS = [
    {
        "images": [str(NAIL_IMG_DIR / "手图/手图/001.jpg")],
        "content": (
            "清透裸粉本甲光疗，干干净净的美最耐看✨\n\n"
            "没有花哨的装饰，只做了建构和加固，指甲看起来饱满健康有光泽。"
            "这种冰透果冻质感真的太适合夏天了，日常通勤完全不会突兀，百搭所有穿搭～\n\n"
            "而且养了三个月的本甲，指缘死皮定期修剪，现在不做款式也很有质感。"
            "推荐给喜欢极简风的姐妹们！"
        ),
        "tags": ["裸透美甲", "极简风", "本甲光疗", "夏日美甲", "日式美甲"],
        "user_id": "user_test_001",
    },
    {
        "images": [str(NAIL_IMG_DIR / "手图/手图/005.jpg")],
        "content": (
            "秋冬必备的酒红渐变！🍷\n\n"
            "透明底胶做出指尖深红酒红晕染，像喝了红酒后的微醺感。"
            "这个颜色巨显白，黄皮姐妹放心冲！\n\n"
            "长梯形甲型拉长手指线条，搭配大衣毛衣都超有气质。"
            "过年回家、年会、约会都合适，一抹酒红气场全开～"
        ),
        "tags": ["酒红美甲", "渐变美甲", "显白美甲", "秋冬美甲", "气质美甲"],
        "user_id": "user_test_002",
    },
    {
        "images": [str(NAIL_IMG_DIR / "款式图/增强后款式图/005.jpg")],
        "content": (
            "被美甲师种草的小众ins风！🐄\n\n"
            "白色纯色跳黑色奶牛纹，再配一条细法式边，可爱又不失精致。"
            "短甲做这个图案也完全hold得住！\n\n"
            "春夏搭配白T牛仔裤就是清纯女高本人～"
            "今年奶牛纹真的好火，做了绝不撞款！"
        ),
        "tags": ["奶牛纹美甲", "法式美甲", "ins风", "小众美甲", "短甲美甲"],
        "user_id": "user_test_003",
    },
    {
        "images": [str(NAIL_IMG_DIR / "款式图/增强后款式图/008.jpg")],
        "content": (
            "气场全开的一款！🖤\n\n"
            "裸透底色配上锐利的黑色法式边，指尖点缀几颗小水钻，高级感拉满。"
            "长尖甲型攻击性十足，适合气场强大的姐妹。\n\n"
            "晚宴、派对、约会都是绝杀，搭配黑色小礼服简直不要太飒！"
            "做完美甲师都说这手可以直接去走红毯了😂"
        ),
        "tags": ["黑色法式", "水钻美甲", "欧美风", "气场美甲", "派对美甲"],
        "user_id": "user_test_001",
    },
    {
        "images": [str(NAIL_IMG_DIR / "款式图/增强后款式图/001.jpg")],
        "content": (
            "安利一万遍的裸米色纯色美甲！🤍\n\n"
            "这个颜色就是温柔本身，不挑肤色不挑场合，做了它就是韩剧女主手上那种感觉。"
            "短圆甲显得手很嫩很乖，学生党、上班族都适合。\n\n"
            "纯色美甲永远不会过时，而且这个裸米色比纯白更柔和，比裸粉更高级，"
            "真的是我做过最满意的纯色了！"
        ),
        "tags": ["裸色美甲", "温柔风", "韩系美甲", "纯色美甲", "通勤美甲"],
        "user_id": "user_test_002",
    },
    {
        "images": [str(NAIL_IMG_DIR / "手图/手图/010.jpg")],
        "content": (
            "细节控会爱死这款！💎\n\n"
            "裸透底色配白色细闪法式边，近看有淡淡的闪粉光泽，低调优雅又不失精致。"
            "阳光下微微反光真的美哭了。\n\n"
            "结婚订婚或者日常约会都超合适，那种不经意的精致感最动人。"
            "美甲师画法式边的手艺绝了，线条又细又匀！"
        ),
        "tags": ["细闪法式", "白色美甲", "精致美甲", "约会美甲", "新娘美甲"],
        "user_id": "user_test_003",
    },
    {
        "images": [str(NAIL_IMG_DIR / "手图/手图/009.jpg")],
        "content": (
            "停掉美甲三个月，本甲终于养回来了！💪\n\n"
            "坚持涂营养油和加固胶，指缘死皮定期修剪，甲面打磨抛光。"
            "现在指甲水光透亮，健康的指甲本身就是最美的装饰～\n\n"
            "分享几个养甲小tips：\n"
            "1. 每天涂指缘油，保持滋润\n"
            "2. 不要用指甲抠东西\n"
            "3. 定期做建构，增加指甲硬度\n"
            "4. 饮食多吃蛋白质和生物素\n\n"
            "养甲是一场修行，但真的值得！"
        ),
        "tags": ["护甲养甲", "本甲养护", "自然美甲", "美甲护理", "养甲心得"],
        "user_id": "user_test_001",
    },
    {
        "images": [
            str(NAIL_IMG_DIR / "款式图/原始款式图/003.jpg"),
            str(NAIL_IMG_DIR / "款式图/原始款式图/007.jpg"),
        ],
        "content": (
            "春夏最爱的两款美甲合集来啦！🌸\n\n"
            "第一款是温柔到骨子里的粉嫩系，搭配小碎花或者纯色裙子都好看。"
            "第二款偏知性优雅风，适合上班或者正式一点场合。\n\n"
            "两款都很适合春夏，颜色明媚但不张扬，做了之后每天都忍不住看自己的手～"
            "姐妹们更喜欢哪一款？评论区告诉我！"
        ),
        "tags": ["春夏美甲", "美甲合集", "粉嫩美甲", "知性风", "日常美甲"],
        "user_id": "user_test_002",
    },
]


def copy_image(src_path: str) -> tuple[str, str]:
    """Copy image to community dir, return (file_id, dest_path)."""
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {src_path}")

    file_id = uuid.uuid4().hex[:12]
    ext = src.suffix.lower()
    safe_name = f"{file_id}{ext}"
    dest = COMMUNITY_DIR / safe_name
    shutil.copy2(src, dest)
    return file_id, str(dest)


def main():
    now = datetime.now(UTC).isoformat()
    created = 0

    for i, post_data in enumerate(POSTS):
        post_id = uuid.uuid4().hex[:16]

        # Stagger created_at so posts don't all have same timestamp
        # Each post is ~2 hours apart
        from datetime import timedelta
        post_time = (datetime.now(UTC) - timedelta(hours=i * 3)).isoformat()

        with get_db() as conn:
            conn.execute(
                """INSERT INTO community_posts
                   (id, user_id, content, tags, style_refs, like_count, comment_count, is_active, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,1,?,?)""",
                (
                    post_id,
                    post_data["user_id"],
                    post_data["content"],
                    json.dumps(post_data["tags"], ensure_ascii=False),
                    "[]",
                    # Some random like/comment counts for realism
                    (i * 7 + 3) % 50 + 5,  # 5-54 likes
                    (i * 3 + 1) % 15 + 1,   # 1-16 comments
                    post_time,
                    post_time,
                ),
            )

            for idx, img_src in enumerate(post_data["images"]):
                try:
                    file_id, dest_path = copy_image(img_src)
                except FileNotFoundError as e:
                    print(f"  ⚠ Skipping missing image: {e}")
                    continue

                conn.execute(
                    """INSERT INTO post_images
                       (id, post_id, file_path, filename, sort_order, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (file_id, post_id, dest_path, Path(dest_path).name, idx, post_time),
                )

            # Add some likes from other users for realism
            likers = ["user_test_002", "user_test_003", "user_ops_001"]
            for j, liker_id in enumerate(likers[: (i % 4) + 1]):
                like_id = uuid.uuid4().hex[:12]
                try:
                    conn.execute(
                        "INSERT INTO post_likes (id, post_id, user_id, created_at) VALUES (?,?,?,?)",
                        (like_id, post_id, liker_id, post_time),
                    )
                except Exception:
                    pass  # UNIQUE constraint may hit for duplicate likes, ignore

            # Add some comments for realism
            sample_comments = [
                "好好看！这个颜色太适合夏天了吧✨",
                "求美甲师推荐！在哪里做的呀？",
                "已收藏，下次做美甲就拿着这个图去！",
                "手好白啊，慕了慕了😭",
                "这个能保持多久呀？容易掉吗？",
                "太好看了！同款已经安排上了",
                "收藏了，纠结做什么款式好久了，就这个了！",
                "请问这是甲片还是本甲做的呀？",
            ]
            for j in range((i * 2) % 6):
                comment_id = uuid.uuid4().hex[:12]
                commenter = ["user_test_001", "user_test_002", "user_test_003"][j % 3]
                conn.execute(
                    """INSERT INTO post_comments
                       (id, post_id, user_id, content, parent_id, is_active, created_at)
                       VALUES (?,?,?,?,NULL,1,?)""",
                    (comment_id, post_id, commenter, sample_comments[(i + j) % len(sample_comments)], post_time),
                )

            conn.commit()

        print(f"  ✅ Post {i+1}: {post_data['tags'][0]} ({len(post_data['images'])} images, {post_data['user_id']})")
        created += 1

    print(f"\n🎉 Created {created} posts in community_posts table.")
    print(f"   Images saved to: {COMMUNITY_DIR}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
