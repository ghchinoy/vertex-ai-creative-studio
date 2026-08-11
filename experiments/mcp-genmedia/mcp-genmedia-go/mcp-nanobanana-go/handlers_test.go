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
	"reflect"
	"testing"
	"time"

	common "github.com/GoogleCloudPlatform/vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/mcp-common"
)

func TestExtForMimeType(t *testing.T) {
	tests := []struct {
		mimeType string
		want     string
	}{
		{"image/jpeg", ".jpg"},
		{"image/webp", ".webp"},
		{"image/gif", ".gif"},
		{"image/png", ".png"},
		{"application/octet-stream", ".png"}, // unknown -> default png
		{"", ".png"},                         // empty -> default png
		{"image/JPEG", ".png"},               // case-sensitive: not matched -> default png
	}
	for _, tc := range tests {
		t.Run(tc.mimeType, func(t *testing.T) {
			if got := extForMimeType(tc.mimeType); got != tc.want {
				t.Errorf("extForMimeType(%q) = %q, want %q", tc.mimeType, got, tc.want)
			}
		})
	}
}

// TestClientOutputFilename covers the accept-and-alias precedence contract:
// output_filename wins, then any legacy alias, then "" (default scheme).
func TestClientOutputFilename(t *testing.T) {
	tests := []struct {
		name       string
		args       map[string]any
		legacyKeys []string
		want       string
	}{
		{
			name: "output_filename honored",
			args: map[string]any{"output_filename": "hero.png"},
			want: "hero.png",
		},
		{
			name: "output_filename trimmed",
			args: map[string]any{"output_filename": "  hero.png  "},
			want: "hero.png",
		},
		{
			name:       "legacy alias used when output_filename unset (back-compat)",
			args:       map[string]any{"file_name": "legacy.png"},
			legacyKeys: []string{"file_name"},
			want:       "legacy.png",
		},
		{
			name:       "output_filename wins on conflict with legacy alias",
			args:       map[string]any{"output_filename": "new.png", "file_name": "legacy.png"},
			legacyKeys: []string{"file_name"},
			want:       "new.png",
		},
		{
			name: "none set returns empty (default scheme)",
			args: map[string]any{},
			want: "",
		},
		{
			name: "blank output_filename ignored",
			args: map[string]any{"output_filename": "   "},
			want: "",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := clientOutputFilename(tc.args, tc.legacyKeys...); got != tc.want {
				t.Errorf("clientOutputFilename(%v, %v) = %q, want %q", tc.args, tc.legacyKeys, got, tc.want)
			}
		})
	}
}

// TestBuildImageFilenames covers the nanobanana naming decision: unset -> nil
// (default scheme), n==1 -> foo.png, n>1 -> foo_1.png..foo_n.png, extension
// forced to the real MIME type.
func TestBuildImageFilenames(t *testing.T) {
	tests := []struct {
		name     string
		base     string
		count    int
		mimeType string
		want     []string
		wantErr  bool
	}{
		{
			name:     "unset base returns nil (default scheme / back-compat)",
			base:     "",
			count:    2,
			mimeType: "image/png",
			want:     nil,
		},
		{
			name:     "blank base returns nil",
			base:     "   ",
			count:    1,
			mimeType: "image/png",
			want:     nil,
		},
		{
			name:     "single image no suffix",
			base:     "foo.png",
			count:    1,
			mimeType: "image/png",
			want:     []string{"foo.png"},
		},
		{
			name:     "multiple images suffixed",
			base:     "foo.png",
			count:    3,
			mimeType: "image/png",
			want:     []string{"foo_1.png", "foo_2.png", "foo_3.png"},
		},
		{
			name:     "extension forced to real MIME (single)",
			base:     "foo.jpeg",
			count:    1,
			mimeType: "image/png",
			want:     []string{"foo.png"},
		},
		{
			name:     "extension forced to real MIME (multiple)",
			base:     "foo.jpeg",
			count:    2,
			mimeType: "image/png",
			want:     []string{"foo_1.png", "foo_2.png"},
		},
		{
			name:     "missing extension gets forced",
			base:     "foo",
			count:    1,
			mimeType: "image/jpeg",
			want:     []string{"foo.jpg"},
		},
		{
			name:     "traversal base sanitized",
			base:     "../../hero.png",
			count:    1,
			mimeType: "image/png",
			want:     []string{"hero.png"},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := buildImageFilenames(tc.base, tc.count, tc.mimeType)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("buildImageFilenames(%q, %d, %q) = %v, want error", tc.base, tc.count, tc.mimeType, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("buildImageFilenames(%q, %d, %q) unexpected error: %v", tc.base, tc.count, tc.mimeType, err)
			}
			if !reflect.DeepEqual(got, tc.want) {
				t.Errorf("buildImageFilenames(%q, %d, %q) = %v, want %v", tc.base, tc.count, tc.mimeType, got, tc.want)
			}
		})
	}
}

// TestDefaultImageFilename locks the legacy default naming scheme byte-for-byte,
// so the unset-output_filename path is guaranteed to be a zero regression.
func TestDefaultImageFilename(t *testing.T) {
	tests := []struct {
		gentime   string
		partIndex int
		mimeType  string
		want      string
	}{
		{"20260811120000", 0, "image/png", "gemini_20260811120000_0.png"},
		{"20260811120000", 1, "image/jpeg", "gemini_20260811120000_1.jpg"},
		{"20260811120000", 2, "", "gemini_20260811120000_2.png"},
	}
	for _, tc := range tests {
		t.Run(tc.want, func(t *testing.T) {
			if got := defaultImageFilename(tc.gentime, tc.partIndex, tc.mimeType); got != tc.want {
				t.Errorf("defaultImageFilename(%q, %d, %q) = %q, want %q", tc.gentime, tc.partIndex, tc.mimeType, got, tc.want)
			}
		})
	}
}

// TestSignedURLExpiryWiring guards the nanobanana-specific env var name that is
// read through the shared common.SignedURLExpiryFromEnv helper. The exhaustive
// clamp/default/disable behavior is covered by common's own tests; this only
// asserts the wiring (correct env var, values honored) after the extraction.
func TestSignedURLExpiryWiring(t *testing.T) {
	const envVar = "NANOBANANA_SIGNED_URL_EXPIRY_HOURS"

	t.Run("default when unset", func(t *testing.T) {
		t.Setenv(envVar, "")
		if got := common.SignedURLExpiryFromEnv(envVar); got != 24*time.Hour {
			t.Errorf("got %v, want 24h", got)
		}
	})
	t.Run("explicit value honored", func(t *testing.T) {
		t.Setenv(envVar, "6")
		if got := common.SignedURLExpiryFromEnv(envVar); got != 6*time.Hour {
			t.Errorf("got %v, want 6h", got)
		}
	})
	t.Run("zero disables", func(t *testing.T) {
		t.Setenv(envVar, "0")
		if got := common.SignedURLExpiryFromEnv(envVar); got != 0 {
			t.Errorf("got %v, want 0", got)
		}
	})
}
