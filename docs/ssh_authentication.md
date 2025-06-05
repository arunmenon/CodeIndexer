# SSH Authentication for Private Repositories

CodeIndexer supports SSH authentication for accessing private Git repositories. This guide explains how to set up and use SSH authentication with the indexer.

## Overview

Many private Git repositories (GitHub, GitLab, Bitbucket, etc.) require SSH authentication instead of password authentication. CodeIndexer provides flexible options for SSH authentication to help you access these repositories.

## Setup Options

### Option 1: Using Your Default SSH Keys and Agent

If you already have SSH keys set up and added to your SSH agent, you can simply use:

```bash
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/org/private-repo.git --ssh-auth
```

The `--ssh-auth` flag will:
1. Convert HTTPS URLs to SSH format (e.g., `https://github.com/org/repo.git` → `git@github.com:org/repo.git`)
2. Use your default SSH key configuration and SSH agent

### Option 2: Specifying a Custom SSH Key

If you need to use a specific SSH key that isn't in your agent:

```bash
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/org/private-repo.git --ssh-auth --ssh-key /path/to/your/private_key
```

### Option 3: Using Environment Variables

You can also specify the SSH key using an environment variable:

```bash
export CODEINDEXER_SSH_KEY=/path/to/your/private_key
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/org/private-repo.git --ssh-auth
```

## Troubleshooting SSH Authentication

### Permission Denied Errors

If you get a "Permission denied (publickey)" error:

1. Verify your SSH key is added to your SSH agent:
   ```bash
   ssh-add -l
   ```

2. Check if your key has been added to the Git service:
   - GitHub: https://github.com/settings/keys
   - GitLab: https://gitlab.com/-/profile/keys
   - Bitbucket: https://bitbucket.org/account/settings/ssh-keys/

3. Test SSH connection directly:
   ```bash
   # For GitHub
   ssh -T git@github.com
   
   # For GitLab
   ssh -T git@gitlab.com
   ```

### URL Conversion Issues

If the URL conversion doesn't work properly, you can provide the SSH URL directly:

```bash
python -m code_indexer.ingestion.cli.run_pipeline --repo-path git@github.com:org/private-repo.git --ssh-auth
```

### Using SSH Keys Without a Passphrase

For automated environments, you might want to use an SSH key without a passphrase. However, this is less secure and should only be used in controlled environments.

### Using SSH Keys With a Passphrase

If your SSH key has a passphrase, make sure your SSH agent is running and has the key loaded:

```bash
eval $(ssh-agent -s)
ssh-add /path/to/your/private_key
```

## Best Practices

1. **Security**: Don't embed SSH private keys in your code or commit them to repositories
2. **Key Management**: Use different keys for different services or environments
3. **Passphrase Protection**: Use passphrases with your SSH keys for additional security
4. **Agent Forwarding**: Be cautious with SSH agent forwarding, as it can pose security risks

## Enterprise Git Servers

For enterprise Git servers (like GitHub Enterprise, GitLab Self-Managed), the same authentication methods apply, but you'll need to ensure:

1. The host is recognized in your SSH config or known_hosts file
2. Your SSH key has been added to your profile on the enterprise Git server
3. You may need to adjust the hostname in the SSH URL based on your enterprise configuration

## Docker Integration

If you're running CodeIndexer in a Docker container, you'll need to mount your SSH keys:

```bash
docker run -v ~/.ssh:/root/.ssh:ro -e CODEINDEXER_SSH_KEY=/root/.ssh/id_rsa codeindexer --repo-path https://github.com/org/private-repo.git --ssh-auth
```

## Support for Multi-Key Setups

If you use different SSH keys for different Git hosts, the system will use your SSH configuration from `~/.ssh/config` if available. You can set up host-specific keys there:

```
# Example ~/.ssh/config
Host github.com
  IdentityFile ~/.ssh/github_key

Host gitlab.com
  IdentityFile ~/.ssh/gitlab_key
```

With this configuration, the appropriate key will be used based on the repository host.