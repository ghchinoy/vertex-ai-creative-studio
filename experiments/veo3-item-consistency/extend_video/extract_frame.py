import os

import cv2


# --- Function to extract the last N frames from a video ---
def extract_last_frames(video_path: str, num_frames: int = 4) -> list:
    """Extracts the last 'num_frames' from a video file using OpenCV.

    Args:
        video_path (str): Path to the video file.
        num_frames (int): The number of frames to extract from the end.

    Returns:
        A list of frames, where each frame is a NumPy array.
        Returns an empty list if the video cannot be opened or has no frames.

    """
    if not os.path.exists(video_path):
        # Handle the case where the video file does not exist.
        print(f"Error: Video file not found at: {video_path}")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        # Handle the case where the video file is corrupt or unreadable.
        print(f"Error: Could not open video file: {video_path}")
        return []

    # Get the total number of frames in the video.
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Determine the starting frame for extraction.
    if total_frames < num_frames:
        start_frame = 0
        num_to_extract = total_frames
    else:
        start_frame = total_frames - num_frames
        num_to_extract = num_frames

    # Set the video's reading position to the calculated start frame.
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    extracted_frames = []
    frames_read = 0
    while frames_read < num_to_extract:
        success, frame = cap.read()
        if not success:
            break
        extracted_frames.append(frame)
        frames_read += 1

    cap.release()
    return extracted_frames


def save_frames_to_temp(
    frames: list,
    folder_name: str = "temp",
    prefix: str = "frame_",
) -> str:
    """Saves a list of frames into a local folder in the current directory.

    Args:
        frames (list): A list of frames (as NumPy arrays) to save.
        folder_name (str): The name of the folder to create in the current directory.
        prefix (str): A prefix for the saved image file names.

    Returns:
        The path to the folder where frames were saved.
        Returns an empty string if no frames are provided.

    """
    if not frames:
        print("⚠️ Warning: No frames were provided to save.")
        return ""

    # Create the local folder in the current working directory.
    # The 'exist_ok=True' argument prevents an error if the folder already exists.
    os.makedirs(folder_name, exist_ok=True)
    print(f"✅ Saving frames to local folder: '{os.path.abspath(folder_name)}'")

    for i, frame in enumerate(frames):
        # Construct a full file path for each frame (e.g., temp/frame_000.png).
        file_path = os.path.join(folder_name, f"{prefix}{i:03d}.png")
        # Save the frame to disk as a PNG image.
        cv2.imwrite(file_path, frame)

    return folder_name


if __name__ == "__main__":
    # --- Configuration ---
    video_file = "../output/outpainted_image.mp4"
    num_frames_to_get = 4

    print(f"Starting process for video: '{video_file}'")

    # Step 1: Call the function to extract the last frames.
    last_frames = extract_last_frames(
        video_path=video_file,
        num_frames=num_frames_to_get,
    )

    # Step 2: Check if frames were extracted before trying to save them.
    if last_frames:
        # If extraction was successful, call the function to save the frames.
        folder_path = save_frames_to_temp(frames=last_frames)
        print(f"\n✅ Process complete. Frames saved in: {folder_path}")
    else:
        # Handle the case where no frames were returned.
        print("\n❌ Process failed. Could not extract frames from the video.")
