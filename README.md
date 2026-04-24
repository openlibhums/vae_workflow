# VAE Workflow

A Janeway workflow plugin for managing Voluntary Academic Editor (VAE) article claiming and assignment.

## Requirements

- Janeway 1.7.0+

## Installation

1. Place the `vae_workflow` folder in your Janeway `src/plugins/` directory.
2. Add `plugins.vae_workflow` to `INSTALLED_APPS` in your Janeway settings file.
3. Run the install command:

```bash
python manage.py install_plugins vae_workflow
```

4. In the Janeway manager, add the **VAE Claiming** stage to your journal's workflow.

## Configuration

Once installed, navigate to the VAE Workflow manager to:

- Add and remove VAEs from the pool
- View articles currently in the claiming stage

## How it works

1. An editor moves an article into the **VAE Claiming** stage.
2. VAEs in the pool can view available articles and claim one as Handling Editor.
3. Once claimed, the article is assigned to that VAE for further handling.

## License

This plugin is licensed under the same terms as Janeway. See the [Janeway repository](https://github.com/BirkbeckCTP/janeway) for details.
