import cv2
import numpy as np
from scipy.fftpack import fft, ifft
from scipy.signal import butter, filtfilt
import argparse
import os

class PhaseBasedMotionMagnification:
    def __init__(self, amplification=50, low_freq=0.5, high_freq=10, pyramid_levels=4):
        """
        Phase-based motion magnification for vibration analysis
        
        Parameters:
        - amplification: Motion amplification factor (10-100 typical for vibrations)
        - low_freq: Low cutoff frequency (Hz)
        - high_freq: High cutoff frequency (Hz) 
        - pyramid_levels: Number of pyramid levels for spatial filtering
        """
        self.amplification = amplification
        self.low_freq = low_freq
        self.high_freq = high_freq
        self.pyramid_levels = pyramid_levels
        
    def build_gaussian_pyramid(self, frame):
        """Build Gaussian pyramid for spatial filtering"""
        pyramid = [frame.astype(np.float32)]
        
        for i in range(self.pyramid_levels):
            # Downsample by factor of 2
            frame = cv2.pyrDown(frame)
            pyramid.append(frame.astype(np.float32))
            
        return pyramid
    
    def reconstruct_from_pyramid(self, pyramid):
        """Reconstruct image from Gaussian pyramid"""
        frame = pyramid[-1]
        
        for i in range(len(pyramid) - 2, -1, -1):
            # Upsample and add
            frame = cv2.pyrUp(frame)
            # Ensure size compatibility
            h, w = pyramid[i].shape[:2]
            frame = cv2.resize(frame, (w, h))
            frame += pyramid[i]
            
        return np.clip(frame, 0, 255).astype(np.uint8)
    
    def temporal_bandpass_filter(self, pyramid_stack, fps):
        """Apply temporal bandpass filter to pyramid stack"""
        print(f"Applying temporal filter: {self.low_freq}-{self.high_freq} Hz")
        
        # Convert to frequency domain
        fft_stack = []
        for level in range(len(pyramid_stack[0])):
            # Stack all frames for this pyramid level
            level_stack = np.array([frame[level] for frame in pyramid_stack])
            
            # Apply FFT along temporal axis
            fft_frames = np.fft.fft(level_stack, axis=0)
            
            # Create frequency mask
            freqs = np.fft.fftfreq(len(pyramid_stack), 1/fps)
            mask = (np.abs(freqs) >= self.low_freq) & (np.abs(freqs) <= self.high_freq)
            
            # Apply filter
            fft_frames[~mask] = 0
            
            # Convert back to time domain
            filtered_frames = np.real(np.fft.ifft(fft_frames, axis=0))
            fft_stack.append(filtered_frames)
            
        return fft_stack
    
    def amplify_motion(self, pyramid_stack, filtered_stack):
        """Amplify the filtered motion"""
        amplified_stack = []
        
        for frame_idx in range(len(pyramid_stack)):
            amplified_pyramid = []
            
            for level in range(len(pyramid_stack[0])):
                # Get original and filtered frames
                original = pyramid_stack[frame_idx][level]
                filtered = filtered_stack[level][frame_idx]
                
                # Amplify and add back
                amplified = original + self.amplification * filtered
                amplified_pyramid.append(amplified)
                
            amplified_stack.append(amplified_pyramid)
            
        return amplified_stack
    
    def process_video(self, input_path, output_path):
        """Process entire video for motion magnification"""
        
        # Open video
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {input_path}")
            
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Processing video: {width}x{height}, {fps}fps, {total_frames} frames")
        print(f"Amplification factor: {self.amplification}")
        print(f"Frequency range: {self.low_freq}-{self.high_freq} Hz")
        
        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Read all frames and build pyramids
        print("Reading frames and building pyramids...")
        pyramid_stack = []
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Convert to grayscale for processing
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Build Gaussian pyramid
            pyramid = self.build_gaussian_pyramid(gray)
            pyramid_stack.append(pyramid)
            
            frame_count += 1
            if frame_count % 50 == 0:
                print(f"Processed {frame_count}/{total_frames} frames")
        
        cap.release()
        print(f"Built pyramids for {len(pyramid_stack)} frames")
        
        # Apply temporal filtering
        print("Applying temporal bandpass filter...")
        filtered_stack = self.temporal_bandpass_filter(pyramid_stack, fps)
        
        # Amplify motion
        print("Amplifying motion...")
        amplified_stack = self.amplify_motion(pyramid_stack, filtered_stack)
        
        # Reconstruct and write frames
        print("Reconstructing and writing output...")
        for i, amplified_pyramid in enumerate(amplified_stack):
            # Reconstruct frame
            amplified_frame = self.reconstruct_from_pyramid(amplified_pyramid)
            
            # Convert back to BGR for output
            if len(amplified_frame.shape) == 2:
                amplified_frame = cv2.cvtColor(amplified_frame, cv2.COLOR_GRAY2BGR)
            
            out.write(amplified_frame)
            
            if i % 50 == 0:
                print(f"Wrote {i+1}/{len(amplified_stack)} frames")
        
        out.release()
        print(f"Motion magnification complete! Output saved to: {output_path}")
        
    def process_video_with_contrast_options(self, input_path, output_base_path):
        """Process video with multiple contrast and frequency options"""
        
        # Open video
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {input_path}")
            
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Processing video: {width}x{height}, {fps}fps, {total_frames} frames")
        
        # Read all frames and build pyramids
        print("Reading frames and building pyramids...")
        pyramid_stack = []
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Convert to grayscale for processing
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Build Gaussian pyramid
            pyramid = self.build_gaussian_pyramid(gray)
            pyramid_stack.append(pyramid)
            
            frame_count += 1
            if frame_count % 50 == 0:
                print(f"Processed {frame_count}/{total_frames} frames")
        
        cap.release()
        print(f"Built pyramids for {len(pyramid_stack)} frames")
        
        # Create multiple outputs with different settings
        contrast_options = [
            {
                'name': 'high_contrast',
                'low_freq': 0.5,
                'high_freq': 15.0,
                'amplification': 80,
                'contrast_factor': 2.0
            },
            {
                'name': 'focused_motion',
                'low_freq': 40.0,
                'high_freq': 70.0,
                'amplification': 60,
                'contrast_factor': 1.5
            },
            {
                'name': 'broad_spectrum',
                'low_freq': 1.0,
                'high_freq': 30.0,
                'amplification': 70,
                'contrast_factor': 1.8
            }
        ]
        
        for option in contrast_options:
            print(f"\nCreating {option['name']} version...")
            
            # Temporarily set parameters
            original_low = self.low_freq
            original_high = self.high_freq
            original_amp = self.amplification
            
            self.low_freq = option['low_freq']
            self.high_freq = option['high_freq']
            self.amplification = option['amplification']
            
            # Apply temporal filtering
            filtered_stack = self.temporal_bandpass_filter(pyramid_stack, fps)
            
            # Amplify motion
            amplified_stack = self.amplify_motion(pyramid_stack, filtered_stack)
            
            # Setup video writer
            output_path = f"{output_base_path}_{option['name']}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # Reconstruct and write frames with contrast enhancement
            for i, amplified_pyramid in enumerate(amplified_stack):
                # Reconstruct frame
                amplified_frame = self.reconstruct_from_pyramid(amplified_pyramid)
                
                # Apply contrast enhancement
                if len(amplified_frame.shape) == 2:
                    # Grayscale - enhance contrast
                    amplified_frame = cv2.convertScaleAbs(
                        amplified_frame, 
                        alpha=option['contrast_factor'], 
                        beta=0
                    )
                    # Convert to BGR for output
                    amplified_frame = cv2.cvtColor(amplified_frame, cv2.COLOR_GRAY2BGR)
                else:
                    # Color - enhance each channel
                    enhanced = cv2.convertScaleAbs(
                        amplified_frame, 
                        alpha=option['contrast_factor'], 
                        beta=0
                    )
                    amplified_frame = enhanced
                
                out.write(amplified_frame)
                
                if i % 100 == 0:
                    print(f"  Wrote {i+1}/{len(amplified_stack)} frames")
            
            out.release()
            print(f"✅ Created: {output_path}")
            
            # Restore original parameters
            self.low_freq = original_low
            self.high_freq = original_high
            self.amplification = original_amp
    
    def analyze_vibration_frequencies(self, input_path, roi=None, slow_motion_factor=1.0):
        """
        Analyze dominant vibration frequencies in the video
        
        Parameters:
        - roi: Region of interest (x, y, w, h) to focus analysis
        - slow_motion_factor: Factor to convert slow-motion to real-time (e.g., 240fps = 8x slower)
        """
        cap = cv2.VideoCapture(input_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        print(f"Video FPS: {fps}")
        print(f"Slow-motion factor: {slow_motion_factor}x")
        print(f"Real-time equivalent FPS: {fps * slow_motion_factor:.1f}")
        
        # Collect pixel intensity over time
        intensities = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Use ROI if specified, otherwise use center region
            if roi:
                x, y, w, h = roi
                region = gray[y:y+h, x:x+w]
            else:
                h, w = gray.shape
                region = gray[h//4:3*h//4, w//4:3*w//4]
            
            # Average intensity in region
            avg_intensity = np.mean(region)
            intensities.append(avg_intensity)
        
        cap.release()
        
        # Frequency analysis
        intensities = np.array(intensities)
        fft_result = np.fft.fft(intensities)
        freqs = np.fft.fftfreq(len(intensities), 1/fps)
        
        # Convert to real-time frequencies
        real_time_freqs = freqs * slow_motion_factor
        
        # Find dominant frequencies
        magnitude = np.abs(fft_result)
        positive_freqs = real_time_freqs[real_time_freqs > 0]
        positive_magnitude = magnitude[real_time_freqs > 0]
        
        # Get top 10 frequencies for better analysis
        top_indices = np.argsort(positive_magnitude)[-10:][::-1]
        dominant_freqs = positive_freqs[top_indices]
        dominant_magnitudes = positive_magnitude[top_indices]
        
        print("\nDominant frequencies detected (real-time):")
        for i, (freq, mag) in enumerate(zip(dominant_freqs, dominant_magnitudes)):
            print(f"{i+1}. {freq:.2f} Hz (magnitude: {mag:.1f})")
        
        # Categorize frequencies
        lighting_freqs = []
        motion_freqs = []
        
        for freq in dominant_freqs:
            if freq < 0.5:  # Very low frequencies likely lighting changes
                lighting_freqs.append(freq)
            elif freq > 0.5:  # Higher frequencies likely actual motion
                motion_freqs.append(freq)
        
        print(f"\n📊 Analysis Summary:")
        print(f"   • Likely lighting changes: {len(lighting_freqs)} frequencies")
        print(f"   • Likely motion/vibrations: {len(motion_freqs)} frequencies")
        
        if motion_freqs:
            print(f"   • Primary motion frequency: {motion_freqs[0]:.2f} Hz")
        
        return dominant_freqs, motion_freqs, lighting_freqs

    def spatial_motion_filter(self, frame1, frame2, threshold=5):
        """
        Filter out lighting changes by focusing on spatial gradients
        Returns motion mask where actual motion occurred
        """
        # Convert to grayscale
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY) if len(frame1.shape) == 3 else frame1
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY) if len(frame2.shape) == 3 else frame2
        
        # Compute spatial gradients
        grad_x1 = cv2.Sobel(gray1, cv2.CV_64F, 1, 0, ksize=3)
        grad_y1 = cv2.Sobel(gray1, cv2.CV_64F, 0, 1, ksize=3)
        grad_x2 = cv2.Sobel(gray2, cv2.CV_64F, 1, 0, ksize=3)
        grad_y2 = cv2.Sobel(gray2, cv2.CV_64F, 0, 1, ksize=3)
        
        # Compute gradient magnitude
        mag1 = np.sqrt(grad_x1**2 + grad_y1**2)
        mag2 = np.sqrt(grad_x2**2 + grad_y2**2)
        
        # Motion mask based on gradient changes
        motion_mask = np.abs(mag2 - mag1) > threshold
        
        return motion_mask.astype(np.uint8) * 255

    def create_vibration_heatmap(self, input_path, output_path, frequency_range=(0.5, 200)):
        """
        Create a heatmap showing vibration intensity averaged across the entire video
        
        Parameters:
        - input_path: Input video path
        - output_path: Output heatmap image path
        - frequency_range: Tuple of (low_freq, high_freq) to analyze
        """
        print(f"Creating vibration intensity heatmap...")
        print(f"Frequency range: {frequency_range[0]}-{frequency_range[1]} Hz")
        
        cap = cv2.VideoCapture(input_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Initialize heatmap accumulator
        heatmap = np.zeros((height, width), dtype=np.float32)
        frame_count = 0
        
        # Read all frames and accumulate motion
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            
            # Build pyramid for this frame
            pyramid = self.build_gaussian_pyramid(gray)
            
            # Store pyramid for temporal filtering
            if frame_count == 0:
                pyramid_stack = [pyramid]
            else:
                pyramid_stack.append(pyramid)
            
            frame_count += 1
            if frame_count % 50 == 0:
                print(f"Processed {frame_count} frames for heatmap...")
        
        cap.release()
        
        if len(pyramid_stack) < 2:
            print("Not enough frames for analysis")
            return
        
        # Apply temporal filtering to get motion components
        print("Applying temporal filtering for heatmap...")
        self.low_freq = frequency_range[0]
        self.high_freq = frequency_range[1]
        filtered_stack = self.temporal_bandpass_filter(pyramid_stack, fps)
        
        # Accumulate motion intensity across all frames
        print("Accumulating motion intensity...")
        for frame_idx in range(len(pyramid_stack)):
            # Reconstruct motion frame from filtered pyramid
            motion_pyramid = []
            for level in range(len(pyramid_stack[0])):
                motion_frame = filtered_stack[level][frame_idx]
                motion_pyramid.append(motion_frame)
            
            # Reconstruct full resolution motion frame
            motion_frame = self.reconstruct_from_pyramid(motion_pyramid)
            
            # Add absolute motion intensity to heatmap
            heatmap += np.abs(motion_frame.astype(np.float32))
        
        # Average across time
        heatmap /= len(pyramid_stack)
        
        # Normalize heatmap for visualization
        heatmap_normalized = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX)
        heatmap_uint8 = heatmap_normalized.astype(np.uint8)
        
        # Apply color mapping for better visualization
        heatmap_colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
        
        # Add text overlay with statistics
        max_intensity = np.max(heatmap)
        mean_intensity = np.mean(heatmap)
        std_intensity = np.std(heatmap)
        
        # Create text overlay
        text_overlay = np.zeros_like(heatmap_colored)
        cv2.putText(text_overlay, f"Max: {max_intensity:.2f}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(text_overlay, f"Mean: {mean_intensity:.2f}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(text_overlay, f"Std: {std_intensity:.2f}", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(text_overlay, f"Freq: {frequency_range[0]}-{frequency_range[1]} Hz", (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Combine heatmap with text
        final_heatmap = cv2.addWeighted(heatmap_colored, 0.8, text_overlay, 0.2, 0)
        
        # Save grayscale heatmap only
        cv2.imwrite(output_path, heatmap_uint8)
        print(f"Grayscale heatmap saved to: {output_path}")
        
        return heatmap, max_intensity, mean_intensity, std_intensity

    def create_frequency_amplitude_heatmap(self, input_path, output_path, frequency_bins=10):
        """
        Create a heatmap encoding frequency by color and amplitude by brightness
        Uses efficient FFT-based approach to process all frequencies simultaneously
        
        Parameters:
        - input_path: Input video path
        - output_path: Output heatmap image path
        - frequency_bins: Number of frequency bins to analyze
        """
        print(f"Creating frequency-amplitude heatmap (efficient FFT method)...")
        
        cap = cv2.VideoCapture(input_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"Video: {width}x{height}, {fps}fps")
        
        # Read all frames into a 3D array (height, width, time)
        print("Reading all frames...")
        frames = []
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            frames.append(gray)
            frame_count += 1
            
            if frame_count % 50 == 0:
                print(f"Read {frame_count} frames...")
        
        cap.release()
        
        if len(frames) < 2:
            print("Not enough frames for analysis")
            return
        
        # Convert to 3D numpy array
        video_stack = np.array(frames)  # Shape: (time, height, width)
        print(f"Video stack shape: {video_stack.shape}")
        
        # Apply FFT along time axis for each pixel
        print("Applying FFT to all pixels simultaneously...")
        fft_result = np.fft.fft(video_stack, axis=0)
        
        # Get frequency array
        freqs = np.fft.fftfreq(len(frames), 1/fps)
        positive_freqs = freqs[freqs > 0]
        positive_fft = fft_result[freqs > 0]  # Only positive frequencies
        
        print(f"FFT shape: {positive_fft.shape}")
        print(f"Frequency range: {positive_freqs[0]:.2f} - {positive_freqs[-1]:.2f} Hz")
        
        # Create frequency bins
        max_freq = fps / 2  # Nyquist frequency
        freq_bin_edges = np.linspace(0, max_freq, frequency_bins + 1)
        freq_bin_centers = (freq_bin_edges[:-1] + freq_bin_edges[1:]) / 2
        
        print(f"Frequency bins: {freq_bin_centers}")
        
        # Initialize frequency-amplitude heatmap
        freq_amp_heatmap = np.zeros((height, width, frequency_bins), dtype=np.float32)
        
        # Process each frequency bin
        for bin_idx in range(frequency_bins):
            low_freq = freq_bin_edges[bin_idx]
            high_freq = freq_bin_edges[bin_idx + 1]
            
            # Find frequencies in this bin
            mask = (positive_freqs >= low_freq) & (positive_freqs < high_freq)
            
            if np.any(mask):
                # Sum amplitudes for frequencies in this bin
                bin_amplitudes = np.abs(positive_fft[mask])
                freq_amp_heatmap[:, :, bin_idx] = np.sum(bin_amplitudes, axis=0)
        
        # Normalize across frequency bins for each pixel
        print("Normalizing frequency bins...")
        for y in range(height):
            for x in range(width):
                pixel_amplitudes = freq_amp_heatmap[y, x, :]
                if np.sum(pixel_amplitudes) > 0:
                    freq_amp_heatmap[y, x, :] = pixel_amplitudes / np.sum(pixel_amplitudes)
        
        # Create color-coded heatmap
        print("Creating color-coded heatmap...")
        heatmap_hsv = np.zeros((height, width, 3), dtype=np.float32)
        
        for y in range(height):
            for x in range(width):
                # Find the frequency bin with maximum amplitude at this pixel
                amplitudes = freq_amp_heatmap[y, x, :]
                max_amp_idx = np.argmax(amplitudes)
                max_amplitude = amplitudes[max_amp_idx]
                
                # Set HSV values
                # Hue: frequency bin (0-1, maps to 0-180 for OpenCV)
                hue = (max_amp_idx / frequency_bins) * 180
                
                # Saturation: fixed at 255 for full color
                saturation = 255
                
                # Value: amplitude (brightness)
                value = max_amplitude * 255
                
                heatmap_hsv[y, x] = [hue, saturation, value]
        
        # Convert HSV to BGR for saving
        heatmap_bgr = cv2.cvtColor(heatmap_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        # Add color legend
        legend_height = 120
        legend_width = width
        legend = np.zeros((legend_height, legend_width, 3), dtype=np.uint8)
        
        for i in range(legend_width):
            hue = (i / legend_width) * 180
            legend[:, i] = [hue, 255, 255]
        
        legend_bgr = cv2.cvtColor(legend, cv2.COLOR_HSV2BGR)
        
        # Add text to legend
        cv2.putText(legend_bgr, f"Frequency (Hz): {freq_bin_centers[0]:.1f} - {freq_bin_centers[-1]:.1f}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(legend_bgr, "Color = Dominant Frequency", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(legend_bgr, "Brightness = Relative Amplitude", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Combine heatmap with legend
        combined = np.vstack([heatmap_bgr, legend_bgr])
        
        # Save combined heatmap
        cv2.imwrite(output_path, combined)
        print(f"Frequency-amplitude heatmap saved to: {output_path}")
        
        # Also save frequency bin data for analysis
        np.save(output_path.replace('.png', '_data.npy'), freq_amp_heatmap)
        print(f"Frequency bin data saved to: {output_path.replace('.png', '_data.npy')}")
        
        return freq_amp_heatmap, freq_bin_centers

def main():
    # Get all video files from input_videos directory
    input_videos_dir = "/Users/emmiefitz-gibbon/Desktop/sam-website-project/vibration_analysis/input_videos"
    
    # Supported video extensions
    video_extensions = ['.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv']
    
    # Find all video files
    input_videos = []
    if os.path.exists(input_videos_dir):
        for filename in os.listdir(input_videos_dir):
            if any(filename.lower().endswith(ext) for ext in video_extensions):
                input_videos.append(os.path.join(input_videos_dir, filename))
    
    if not input_videos:
        print(f"No video files found in {input_videos_dir}")
        print(f"Supported formats: {', '.join(video_extensions)}")
        return
    
    print(f"Found {len(input_videos)} video files to analyze:")
    for video in input_videos:
        print(f"  • {os.path.basename(video)}")
    print()
    
    # Create magnification processor with broader frequency range
    magnifier = PhaseBasedMotionMagnification(
        amplification=50,  # Moderate amplification for subtle vibrations
        low_freq=0.5,      # Low frequency cutoff
        high_freq=200,     # High frequency cutoff (increased for 170 Hz motor)
        pyramid_levels=4
    )
    
    # iPhone 240fps slow-motion is typically 8x slower than real-time
    slow_motion_factor = 8.0
    
    for input_video in input_videos:
        if not os.path.exists(input_video):
            print(f"Error: Input file {input_video} not found")
            continue
        
        print(f"\n{'='*60}")
        print(f"ANALYZING VIDEO: {os.path.basename(input_video)}")
        print(f"{'='*60}")
        
        # Extract base name for output files
        base_name = os.path.splitext(os.path.basename(input_video))[0]
        
        # First analyze to detect dominant frequencies (accounting for 240fps slow-motion)
        print(f"\n=== FREQUENCY ANALYSIS ===")
        dominant_freqs, motion_freqs, lighting_freqs = magnifier.analyze_vibration_frequencies(
            input_video, slow_motion_factor=slow_motion_factor
        )
        
        print(f"\n🎯 Expected 60 Hz motor frequency analysis:")
        print(f"   • At 30fps recording: 60 Hz will alias to {60 % 15:.1f} Hz")
        print(f"   • At 240fps equivalent: {60 * 8:.1f} Hz")
        
        # Create output directories
        heatmap_dir = f"/Users/emmiefitz-gibbon/Desktop/sam-website-project/vibration_analysis/heatmaps"
        video_dir = f"/Users/emmiefitz-gibbon/Desktop/sam-website-project/vibration_analysis/motion_videos"
        data_dir = f"/Users/emmiefitz-gibbon/Desktop/sam-website-project/vibration_analysis/analysis_data"
        
        os.makedirs(heatmap_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        
        # Create heatmaps for different frequency ranges (grayscale only)
        print(f"\n=== CREATING VIBRATION HEATMAPS ===")
        heatmap_ranges = [
            ("broad", 0.5, 200, "Broad range (0.5-200 Hz)")
        ]
        
        for range_name, low_freq, high_freq, description in heatmap_ranges:
            print(f"\n=== CREATING HEATMAP: {description.upper()} ===")
            
            heatmap_path = f"{heatmap_dir}/{base_name}_{range_name}_heatmap.png"
            
            try:
                heatmap, max_int, mean_int, std_int = magnifier.create_vibration_heatmap(
                    input_video, heatmap_path, frequency_range=(low_freq, high_freq)
                )
                print(f"✅ {description} heatmap complete: {heatmap_path}")
                print(f"   • Max intensity: {max_int:.2f}")
                print(f"   • Mean intensity: {mean_int:.2f}")
                print(f"   • Std intensity: {std_int:.2f}")
            except Exception as e:
                print(f"❌ Error creating {description} heatmap: {e}")
        
        # Create frequency-amplitude heatmap
        print(f"\n=== CREATING FREQUENCY-AMPLITUDE HEATMAP ===")
        freq_amp_path = f"{heatmap_dir}/{base_name}_frequency_amplitude_heatmap.png"
        
        try:
            freq_amp_data, freq_ranges = magnifier.create_frequency_amplitude_heatmap(
                input_video, freq_amp_path, frequency_bins=12
            )
            print(f"✅ Frequency-amplitude heatmap complete: {freq_amp_path}")
            print(f"   • Frequency bins: {len(freq_ranges)}")
            print(f"   • Frequency range: {freq_ranges[0]:.1f}-{freq_ranges[-1]:.1f} Hz")
            
            # Save frequency bin data
            data_path = f"{data_dir}/{base_name}_frequency_data.npy"
            np.save(data_path, freq_amp_data)
            print(f"   • Frequency data saved: {data_path}")
        except Exception as e:
            print(f"❌ Error creating frequency-amplitude heatmap: {e}")
        
        # Check if video is too large for motion magnification
        cap = cv2.VideoCapture(input_video)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        memory_estimate = width * height * total_frames * 4 / 1024 / 1024  # MB
        
        if memory_estimate > 2000:  # Skip if > 2GB
            print(f"\n⚠️  Video too large for motion magnification ({memory_estimate:.1f} MB)")
            print("   Skipping motion magnification videos to avoid memory issues")
            print("   Frequency analysis and heatmaps are still available")
        else:
            # Create motion magnification videos
            print(f"\n=== CREATING MOTION MAGNIFICATION VIDEOS ===")
            frequency_ranges = [
                ("broad", 0.5, 200, "Broad range (0.5-200 Hz)")
            ]
            
            for range_name, low_freq, high_freq, description in frequency_ranges:
                print(f"\n=== PROCESSING {description.upper()} ===")
                
                # Update magnifier parameters
                magnifier.low_freq = low_freq
                magnifier.high_freq = high_freq
                
                output_video = f"{video_dir}/{base_name}_{range_name}.mp4"
                
                try:
                    magnifier.process_video(input_video, output_video)
                    print(f"✅ {description} video complete: {output_video}")
                except Exception as e:
                    print(f"❌ Error processing {description} video: {e}")
        
        print(f"\n🎉 Analysis complete for {os.path.basename(input_video)}!")
        print(f"📁 Heatmaps saved to: {heatmap_dir}")
        print(f"📁 Videos saved to: {video_dir}")
        print(f"📁 Data saved to: {data_dir}")
    
    print(f"\n🎉 ALL ANALYSES COMPLETE!")
    print(f"📊 Frequency-amplitude heatmaps show color=frequency, brightness=amplitude")
    print(f"🔍 Check the frequency-amplitude heatmaps for the most detailed analysis!")

if __name__ == "__main__":
    main()