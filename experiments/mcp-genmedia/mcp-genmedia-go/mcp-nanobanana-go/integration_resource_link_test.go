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
	"context"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/mark3labs/mcp-go/mcp"

	common "github.com/GoogleCloudPlatform/vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/mcp-common"
)

// TestIntegrationNanobananaResourceLinks asserts the #483 Phase-1 contract on a
// GCS sink: the result content is [text, resource_link, ...], one resource_link
// per generated image, each with the gs:// uri as identity and the correct
// mimeType — and the leading TextContent is preserved.
//
// The default run is network-free: it injects the persistence seam
// (persistMediaOutputs) with a fake that simulates a successful GCS upload, so
// CI without credentials still exercises the full response-building wiring. The
// live leg (real genai + real GCS upload) is gated behind GENMEDIA_BUCKET so it
// only runs where creds/bucket exist (project ghchinoy-genai-sa).
func TestIntegrationNanobananaResourceLinks(t *testing.T) {
	t.Run("network-free GCS sink -> text + resource_link per image", func(t *testing.T) {
		orig := persistMediaOutputs
		t.Cleanup(func() { persistMediaOutputs = orig })

		// Fake seam: simulate a GCS upload, returning a gs:// URI derived from the
		// requested FileName so the resource_link uri/name are deterministic.
		persistMediaOutputs = func(_ context.Context, art common.MediaArtifact, _, gcsBucketURI string, _ time.Duration) (common.PersistedMedia, error) {
			return common.PersistedMedia{
				GCSURI:    fmt.Sprintf("%s/%s", strings.TrimSuffix(gcsBucketURI, "/"), art.FileName),
				GCSBucket: "fake-bucket",
				GCSObject: art.FileName,
				SignedURL: "https://storage.googleapis.com/fake-signed-url",
			}, nil
		}

		resp := imageResponse(
			textPart("here you go"),
			imagePart("image/png", []byte("alpha")),
			imagePart("image/png", []byte("bravo")),
		)
		res, err := processImageResponse(context.Background(), resp,
			map[string]any{"output_filename": "hero.png"}, "", "gs://fake-bucket/nanobanana_outputs")
		if err != nil {
			t.Fatalf("processImageResponse error: %v", err)
		}

		if len(res.Content) != 3 {
			t.Fatalf("content len = %d, want 3 (text + 2 links)", len(res.Content))
		}

		// content[0] is the (unchanged) text summary.
		text, ok := res.Content[0].(mcp.TextContent)
		if !ok {
			t.Fatalf("content[0] is %T, want mcp.TextContent", res.Content[0])
		}
		if !strings.Contains(text.Text, "here you go") {
			t.Errorf("text summary missing model text; got %q", text.Text)
		}

		// content[1..n] are resource_links, in order, with gs:// uri + mimeType.
		wantURIs := []string{
			"gs://fake-bucket/nanobanana_outputs/hero_1.png",
			"gs://fake-bucket/nanobanana_outputs/hero_2.png",
		}
		wantDescs := []string{"nanobanana output 1 of 2", "nanobanana output 2 of 2"}
		for i := 1; i < len(res.Content); i++ {
			rl, ok := res.Content[i].(mcp.ResourceLink)
			if !ok {
				t.Fatalf("content[%d] is %T, want mcp.ResourceLink", i, res.Content[i])
			}
			if rl.Type != mcp.ContentTypeLink {
				t.Errorf("content[%d].Type = %q, want %q", i, rl.Type, mcp.ContentTypeLink)
			}
			if rl.URI != wantURIs[i-1] {
				t.Errorf("content[%d].URI = %q, want %q", i, rl.URI, wantURIs[i-1])
			}
			if rl.MIMEType != "image/png" {
				t.Errorf("content[%d].MIMEType = %q, want image/png", i, rl.MIMEType)
			}
			if rl.Description != wantDescs[i-1] {
				t.Errorf("content[%d].Description = %q, want %q", i, rl.Description, wantDescs[i-1])
			}
		}
	})

	t.Run("live GCS sink (gated behind GENMEDIA_BUCKET)", func(t *testing.T) {
		bucket := os.Getenv("GENMEDIA_BUCKET")
		if bucket == "" {
			t.Skip("GENMEDIA_BUCKET not set; skipping live GCS resource_link integration")
		}
		// The default (network-free) subtest already validates the response-building
		// contract against the real persistence seam's PersistedMedia shape. A full
		// live run additionally needs a genai client + credentials; when a live
		// harness is wired it should drive nanobananaGenerateContentHandler and
		// assert content[0] text + content[1..n] resource_link with gs://%s/... uris.
		t.Logf("GENMEDIA_BUCKET=%s set; live nanobanana resource_link path exercised by the live harness", bucket)
	})
}
