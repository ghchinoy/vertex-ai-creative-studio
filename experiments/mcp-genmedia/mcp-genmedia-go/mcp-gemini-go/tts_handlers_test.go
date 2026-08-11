// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"strings"
	"testing"
)

// TestResolveGeminiTTSFilename covers the gemini-TTS naming decision: output_filename
// wins over the deprecated output_filename_prefix, the extension is forced to the
// true audio MIME of the selected encoding, traversal is sanitized, and the legacy
// <prefix>-<voice>-<timestamp><ext> scheme is preserved when output_filename is unset.
func TestResolveGeminiTTSFilename(t *testing.T) {
	const voice = "Callirrhoe"

	t.Run("output_filename honored, extension kept", func(t *testing.T) {
		got, err := resolveGeminiTTSFilename(map[string]any{"output_filename": "speech.wav"}, voice, ".wav", "audio/wav")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "speech.wav" {
			t.Errorf("got %q, want %q", got, "speech.wav")
		}
	})

	t.Run("extension forced to encoding MIME", func(t *testing.T) {
		// Client passes .wav but selected encoding is MP3 -> forced to .mp3.
		got, err := resolveGeminiTTSFilename(map[string]any{"output_filename": "speech.wav"}, voice, ".mp3", "audio/mpeg")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "speech.mp3" {
			t.Errorf("got %q, want %q", got, "speech.mp3")
		}
	})

	t.Run("missing extension gets forced", func(t *testing.T) {
		got, err := resolveGeminiTTSFilename(map[string]any{"output_filename": "speech"}, voice, ".ogg", "audio/ogg")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "speech.ogg" {
			t.Errorf("got %q, want %q", got, "speech.ogg")
		}
	})

	t.Run("output_filename wins over legacy prefix", func(t *testing.T) {
		got, err := resolveGeminiTTSFilename(map[string]any{
			"output_filename":        "speech.wav",
			"output_filename_prefix": "legacy",
		}, voice, ".wav", "audio/wav")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "speech.wav" {
			t.Errorf("got %q, want %q", got, "speech.wav")
		}
	})

	t.Run("traversal sanitized", func(t *testing.T) {
		got, err := resolveGeminiTTSFilename(map[string]any{"output_filename": "../../etc/speech.wav"}, voice, ".wav", "audio/wav")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "speech.wav" {
			t.Errorf("got %q, want %q", got, "speech.wav")
		}
	})

	t.Run("dot-only base errors", func(t *testing.T) {
		if _, err := resolveGeminiTTSFilename(map[string]any{"output_filename": "..."}, voice, ".wav", "audio/wav"); err == nil {
			t.Fatalf("expected error for dot-only base")
		}
	})

	t.Run("legacy prefix scheme preserved when output_filename unset", func(t *testing.T) {
		got, err := resolveGeminiTTSFilename(map[string]any{"output_filename_prefix": "custom"}, voice, ".mp3", "audio/mpeg")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !strings.HasPrefix(got, "custom-"+voice+"-") || !strings.HasSuffix(got, ".mp3") {
			t.Errorf("legacy scheme not preserved: got %q", got)
		}
	})

	t.Run("default prefix when neither set", func(t *testing.T) {
		got, err := resolveGeminiTTSFilename(map[string]any{}, voice, ".wav", "audio/wav")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !strings.HasPrefix(got, "gemini_tts_audio-"+voice+"-") || !strings.HasSuffix(got, ".wav") {
			t.Errorf("default prefix scheme not applied: got %q", got)
		}
	})
}
