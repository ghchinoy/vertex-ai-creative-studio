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

// TestResolveChirpOutputFilename covers the chirp3 naming decision: output_filename
// wins over the deprecated output_filename_prefix, the extension is forced to the
// audio MIME (.wav), traversal is sanitized, and the legacy prefix scheme is
// preserved (with the voice component) when output_filename is unset.
func TestResolveChirpOutputFilename(t *testing.T) {
	const voice = "en-US-Chirp3-HD-Zephyr"

	t.Run("output_filename honored, extension kept", func(t *testing.T) {
		got, err := resolveChirpOutputFilename(map[string]any{"output_filename": "greeting.wav"}, voice)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "greeting.wav" {
			t.Errorf("got %q, want %q", got, "greeting.wav")
		}
	})

	t.Run("wrong extension forced to audio MIME", func(t *testing.T) {
		got, err := resolveChirpOutputFilename(map[string]any{"output_filename": "greeting.mp3"}, voice)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "greeting.wav" {
			t.Errorf("got %q, want %q", got, "greeting.wav")
		}
	})

	t.Run("missing extension gets forced", func(t *testing.T) {
		got, err := resolveChirpOutputFilename(map[string]any{"output_filename": "greeting"}, voice)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "greeting.wav" {
			t.Errorf("got %q, want %q", got, "greeting.wav")
		}
	})

	t.Run("output_filename wins over legacy prefix", func(t *testing.T) {
		got, err := resolveChirpOutputFilename(map[string]any{
			"output_filename":        "greeting.wav",
			"output_filename_prefix": "legacy",
		}, voice)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "greeting.wav" {
			t.Errorf("got %q, want %q", got, "greeting.wav")
		}
	})

	t.Run("traversal sanitized", func(t *testing.T) {
		got, err := resolveChirpOutputFilename(map[string]any{"output_filename": "../../etc/greeting.wav"}, voice)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "greeting.wav" {
			t.Errorf("got %q, want %q", got, "greeting.wav")
		}
	})

	t.Run("dot-only base errors", func(t *testing.T) {
		if _, err := resolveChirpOutputFilename(map[string]any{"output_filename": "..."}, voice); err == nil {
			t.Fatalf("expected error for dot-only base")
		}
	})

	t.Run("legacy prefix scheme preserved when output_filename unset", func(t *testing.T) {
		got, err := resolveChirpOutputFilename(map[string]any{"output_filename_prefix": "custom"}, "en-US/Chirp3:HD")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !strings.HasPrefix(got, "custom-en-US_Chirp3_HD-") || !strings.HasSuffix(got, ".wav") {
			t.Errorf("legacy scheme not preserved: got %q", got)
		}
	})

	t.Run("default prefix when neither set", func(t *testing.T) {
		got, err := resolveChirpOutputFilename(map[string]any{}, voice)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !strings.HasPrefix(got, "chirp_audio-") || !strings.HasSuffix(got, ".wav") {
			t.Errorf("default prefix scheme not applied: got %q", got)
		}
	})
}
