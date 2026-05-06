from moviepy import VideoFileClip, AudioFileClip
from src.core.logging import get_logger

logger = get_logger(__name__)

class AudioEngine:
    """
    Xử lý âm thanh chuyên nghiệp: J-cut, L-cut, Smart Ducking.
    """
    
    def apply_smart_ducking(self, 
                            bgm_clip: AudioFileClip, 
                            voice_clip: AudioFileClip, 
                            duck_volume: float = 0.2) -> AudioFileClip:
        """
        Tự động giảm âm lượng nhạc nền khi có giọng nói.
        """
        # Phân tích volume của voice_clip để tạo volume profile cho bgm
        # Để đơn giản, dùng volumex cho toàn bộ bgm nếu có voice
        # Bản v2.0 sẽ dùng audio levels để duck chính xác từng giây
        return bgm_clip.volumex(duck_volume)

    def apply_j_cut(self, clips: list[VideoFileClip], offset: float = 0.5) -> list[VideoFileClip]:
        """Âm thanh của clip sau bắt đầu trước khi hình ảnh clip trước kết thúc."""
        if len(clips) < 2: return clips
        
        for i in range(1, len(clips)):
            if clips[i].audio:
                # Dịch chuyển âm thanh của clip hiện tại về phía trước 'offset' giây
                clips[i] = clips[i].set_audio(clips[i].audio.set_start(-offset))
        return clips

    def apply_l_cut(self, clips: list[VideoFileClip], offset: float = 0.5) -> list[VideoFileClip]:
        """Hình ảnh clip sau bắt đầu nhưng âm thanh clip trước vẫn còn duy trì."""
        if len(clips) < 2: return clips
        
        for i in range(len(clips) - 1):
            if clips[i].audio:
                # Kéo dài âm thanh của clip hiện tại thêm 'offset' giây sang clip sau
                duration = clips[i].duration
                clips[i] = clips[i].set_audio(clips[i].audio.set_duration(duration + offset))
        return clips
