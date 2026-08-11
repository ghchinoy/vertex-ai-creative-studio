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

import "testing"

// TestResolveLyriaOutputFilename covers the lyria naming decision: output_filename
// wins over the legacy file_name alias, the extension is forced to the audio MIME,
// traversal is sanitized, and unset -> "" (caller uses the shortid default).
func TestResolveLyriaOutputFilename(t *testing.T) {
	tests := []struct {
		name    string
		params  map[string]any
		want    string
		wantErr bool
	}{
		{
			name:   "output_filename honored, extension kept",
			params: map[string]any{"output_filename": "song.wav"},
			want:   "song.wav",
		},
		{
			name:   "wrong extension forced to audio MIME",
			params: map[string]any{"output_filename": "song.mp3"},
			want:   "song.wav",
		},
		{
			name:   "missing extension gets forced",
			params: map[string]any{"output_filename": "song"},
			want:   "song.wav",
		},
		{
			name:   "legacy file_name alias used when output_filename unset",
			params: map[string]any{"file_name": "legacy.wav"},
			want:   "legacy.wav",
		},
		{
			name:   "output_filename wins over legacy file_name",
			params: map[string]any{"output_filename": "new.wav", "file_name": "legacy.wav"},
			want:   "new.wav",
		},
		{
			name:   "traversal sanitized",
			params: map[string]any{"output_filename": "../../etc/song.wav"},
			want:   "song.wav",
		},
		{
			name:   "unset -> empty (shortid default)",
			params: map[string]any{},
			want:   "",
		},
		{
			name:    "dot-only base errors",
			params:  map[string]any{"output_filename": "..."},
			wantErr: true,
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := resolveLyriaOutputFilename(tc.params)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("resolveLyriaOutputFilename(%v) = %q, want error", tc.params, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("resolveLyriaOutputFilename(%v) unexpected error: %v", tc.params, err)
			}
			if got != tc.want {
				t.Errorf("resolveLyriaOutputFilename(%v) = %q, want %q", tc.params, got, tc.want)
			}
		})
	}
}
